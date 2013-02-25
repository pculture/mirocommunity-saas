from django.http import Http404
from localtv.admin.flatpages_views import index

from mirocommunity_saas.models import SiteTierInfo


def flatpages_admin(request):
	"""
	Flatpages should only be editable if custom theming is allowed.

	"""
	tier = SiteTierInfo.objects.get_current().tier
	if not tier.custom_themes:
		raise Http404
	return index(request)
