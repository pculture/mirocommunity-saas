from celery.task import task

from mirocommunity_saas.utils.mail import send_welcome_email


@task(ignore_result=True)
def welcome_email_task(using='default'):
	"""
	Sends the welcome email for this site. The 'using' kwarg is only here
	as part of the settings hack.

	"""
	send_welcome_email()
