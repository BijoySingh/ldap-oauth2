from django.core.urlresolvers import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView, DeleteView
from braces.views import LoginRequiredMixin
from oauth2_provider.views.application import ApplicationOwnerIsUserMixin
from oauth2_provider.models import get_application_model as get_oauth2_application_model
from oauth2_provider.views import AuthorizationView
from oauth2_provider.settings import oauth2_settings
from oauth2_provider.http import HttpResponseUriRedirect
from oauth2_provider.exceptions import OAuthToolkitError

from .forms import RegistrationForm, AllowFormWithRecaptch


class ApplicationRegistrationView(LoginRequiredMixin, CreateView):
    form_class = RegistrationForm
    template_name = "application/application_form_registration.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super(ApplicationRegistrationView, self).form_valid(form)


class ApplicationDetailView(ApplicationOwnerIsUserMixin, DetailView):
    context_object_name = 'application'
    template_name = 'application/application_detail.html'


class ApplicationListView(ApplicationOwnerIsUserMixin, ListView):
    context_object_name = 'applications'
    template_name = 'application/application_list.html'


class ApplicationUpdateView(LoginRequiredMixin, UpdateView):
    """
    View used to update an application owned by the request.user
    """
    form_class = RegistrationForm
    context_object_name = 'application'
    template_name = "application/application_form.html"

    def get_queryset(self):
        return get_oauth2_application_model().objects.filter(user=self.request.user)


class ApplicationDeleteView(ApplicationOwnerIsUserMixin, DeleteView):
    """
    View used to update an application owned by the request.user
    """
    context_object_name = 'application'
    template_name = "application/application_confirm_delete.html"
    success_url = reverse_lazy('oauth:list')


class CustomAuthorizationView(AuthorizationView):
    form_class = AllowFormWithRecaptch

    def form_valid(self, form):
        scopes = form.cleaned_data.get('scope', '')
        scopes = set(scopes.split(' '))
        scopes.add('basic')
        scopes = ' '.join(list(scopes))
        form.cleaned_data['scope'] = scopes
        return super(CustomAuthorizationView, self).form_valid(form)

    def get(self, request, *args, **kwargs):
        """
        Copied blantly from super method. Had to change few stuff, but didn't find better way
        than copying and editing the whole stuff.
        Sin Count += 1
        """
        try:
            scopes, credentials = self.validate_authorization_request(request)
            try:
                del credentials['request']
                # Removing oauthlib.Request from credentials. This is not required in future
            except KeyError:
                pass

            kwargs['scopes_descriptions'] = [oauth2_settings.SCOPES[scope] for scope in scopes]
            kwargs['scopes'] = scopes
            # at this point we know an Application instance with such client_id exists in the database
            application = get_oauth2_application_model().objects.get(
                client_id=credentials['client_id'])  # TODO: cache it!
            kwargs['application'] = application
            kwargs.update(credentials)
            self.oauth2_data = kwargs
            # following two loc are here only because of https://code.djangoproject.com/ticket/17795
            form = self.get_form(self.get_form_class())
            kwargs['form'] = form

            # Check to see if the user has already granted access and return
            # a successful response depending on 'approval_prompt' url parameter
            require_approval = request.GET.get('approval_prompt', oauth2_settings.REQUEST_APPROVAL_PROMPT)

            # If skip_authorization field is True, skip the authorization screen even
            # if this is the first use of the application and there was no previous authorization.
            # This is useful for in-house applications-> assume an in-house applications
            # are already approved.
            if application.skip_authorization:
                uri, headers, body, status = self.create_authorization_response(
                    request=self.request, scopes=" ".join(scopes),
                    credentials=credentials, allow=True)
                return HttpResponseUriRedirect(uri)

            elif require_approval == 'auto':
                tokens = request.user.accesstoken_set.filter(application=kwargs['application']).all().order_by('-id')
                if len(tokens) > 0:
                    token = tokens[0]
                    if len(tokens) > 1:
                        # Enforce one token pair per user policy. Remove all older tokens
                        request.user.accesstoken_set.exclude(pk=token.id).all().delete()

                    # check past authorizations regarded the same scopes as the current one
                    if token.allow_scopes(scopes):
                        uri, headers, body, status = self.create_authorization_response(
                            request=self.request, scopes=" ".join(scopes),
                            credentials=credentials, allow=True)
                        return HttpResponseUriRedirect(uri)

            return self.render_to_response(self.get_context_data(**kwargs))

        except OAuthToolkitError as error:
            return self.error_response(error)
