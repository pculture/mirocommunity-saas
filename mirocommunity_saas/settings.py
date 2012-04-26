from django.conf import settings

DISABLE_THEME_UPLOAD = lambda: not __import__('mirocommunity_saas.models').models.TierInfo.objects.get_current().enforce_permit_custom_template()
USE_ZENDESK = getattr(settings, 'LOCALTV_USE_ZENDESK', False)
DISABLE_TIERS_ENFORCEMENT = getattr(settings,
                                    'LOCALTV_DISABLE_TIERS_ENFORCEMENT', False)
