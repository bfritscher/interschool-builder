
CSRF_TRUSTED_ORIGINS = [os.getenv('DJANGO_ALLOWED_HOST')]
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
USE_X_FORWARDED_HOST = True
EMAIL_BACKEND = "backend.settings.smtp.TagSMTPBackend"
EMAIL_HOST = "mail"
EMAIL_PORT = 1025
EMAIL_USE_TLS = False
EMAIL_USE_SSL = False

