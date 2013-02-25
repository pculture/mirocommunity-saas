from django.contrib.flatpages.middleware import FlatpageFallbackMiddleware

from mirocommunity_saas.models import SiteTierInfo


class TierFlatpageMiddleware(FlatpageFallbackMiddleware):
	"""
	A version of the normal flatpage middleware which only takes effect if
	custom themes are enabled.

	"""
	def process_response(self, request, response):
		tier = SiteTierInfo.objects.get_current().tier
		if not tier.custom_themes:
			return response
		return super(TierFlatpageMiddleware, self).process_response(request,
															        response)
