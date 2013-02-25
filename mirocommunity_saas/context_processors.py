from mirocommunity_saas.models import SiteTierInfo


def tier_info(request):
	return {
		'tier_info': SiteTierInfo.objects.get_current()
	}
