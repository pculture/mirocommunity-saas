from django.conf.urls.defaults import patterns, include, url

# Trigger tiers signal registration.
from mirocommunity_saas.utils import tiers


urlpatterns = patterns('',
    url(r'^admin/', include('mirocommunity_saas.admin.urls')),
    url(r'^', include('localtv.urls'))
)


