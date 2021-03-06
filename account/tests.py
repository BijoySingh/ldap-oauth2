from django.test import TestCase
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.conf import settings


class LoginViewTestCase(TestCase):
    login_url = reverse('account:login')
    next_ = reverse('oauth:list')
    template_name = 'account/login.html'

    def _user_login(self):
        self.client.login(username='test_user', password='test123')

    def setUp(self):
        User.objects.create_user(username='test_user', password='test123')

    def test_user_already_logged_in_get(self):
        """
        Tests the redirect on opening login page when user is already logged in.
        Request must be redirected to settings.LOGIN_REDIRECT_URL when get query 'next' is not present
        """
        self._user_login()
        response = self.client.get(self.login_url)
        self.assertRedirects(response, settings.LOGIN_REDIRECT_URL, target_status_code=404)
        # TODO: On changing LOGIN_REDIRECT_URL fix this as well

    def test_user_already_logged_in_get_with_next(self):
        """
        Tests the redirect on opening login page when user is already logged in.
        Request must be redirected to get query param 'next'
        """
        self._user_login()
        response = self.client.get('%s?next=%s' % (self.login_url, self.next_))
        self.assertRedirects(response, self.next_)

    def test_user_not_logged_in_get(self):
        """
        Test in case user is not logged in. Should return 200 status for 'account:login' page
        """
        response = self.client.get(self.login_url)
        self.assertTemplateUsed(response, self.template_name)
        self.assertEqual(response.status_code, 200)

    def test_user_not_logged_in_get_with_next(self):
        """
        Should not redirect in case 'next' is present in query param and user is not logged in
        """
        response = self.client.get('%s?next=%s' % (self.login_url, self.next_))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, self.template_name)

    def test_post_request_correct_credentials(self):
        response = self.client.post(self.login_url, {'username': 'test_user', 'password': 'test123'})
        self.assertRedirects(response, settings.LOGIN_REDIRECT_URL, target_status_code=404)

    def test_post_request_incorrect_credentials(self):
        response = self.client.post(self.login_url, {'username': 'test', 'password': 'test123'})
        self.assertTemplateUsed(response, self.template_name)
        self.assertEqual(response.status_code, 200)

    def test_post_request_correct_credentials_remember_me(self):
        response = self.client.post(self.login_url, {'username': 'test_user',
                                                     'password': 'test123', 'remember': True})
        self.assertRedirects(response, settings.LOGIN_REDIRECT_URL, target_status_code=404)
        session = self.client.session
        self.assertEqual(session.get_expiry_age(), 24*365*3600)


class LogoutViewTestCase(TestCase):
    logout_url = reverse('account:logout')
    login_url = reverse('account:login')

    def setUp(self):
        User.objects.create_user(username='test_user', password='test123')

    def test_user_logged_in(self):
        """
        Logout should redirect to login page
        """
        self.client.login(username='test_user', password='test123')
        response = self.client.get(self.logout_url)
        self.assertRedirects(response, self.login_url)

    def test_user_not_logged_in(self):
        response = self.client.get(self.logout_url)
        self.assertRedirects(response, self.login_url)

    def test_post(self):
        """
        Assert that POST method is not allowed for logout. Response code should be 405
        """
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, 405)
