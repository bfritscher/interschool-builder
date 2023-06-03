import os

from django.core.mail.backends.smtp import EmailBackend

class TagSMTPBackend(EmailBackend):
    def send_messages(self, email_messages):
        for message in email_messages:
            message.extra_headers['X-Tags'] = os.getenv('PROJECT_NAME')
        return super().send_messages(email_messages)
