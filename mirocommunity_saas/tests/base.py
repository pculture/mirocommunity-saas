# Miro Community - Easiest way to make a video website
#
# Copyright (C) 2010, 2011, 2012 Participatory Culture Foundation
# 
# Miro Community is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
# 
# Miro Community is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with Miro Community.  If not, see <http://www.gnu.org/licenses/>.

import datetime

from localtv.tests.base import BaseTestCase as MCBaseTestCase

from mirocommunity_saas.models import Tier, SiteTierInfo


class BaseTestCase(MCBaseTestCase):
    def create_tier(self, name='Tier', slug='tier', **kwargs):
        return Tier.objects.create(name=name, slug=slug, **kwargs)

    def create_tier_info(self, tier, site_id=1, tier_changed=None,
                         available_tiers=None, ipns=None, **kwargs):
        """
        Factory for creating SiteTierInfo instances. Special behavior:

        * If ``tier_changed`` is ``None``, then it will be set to the current
          time.
        * ``available_tiers`` should be a list (or ``None`` for an empty list)
          of :class:`Tier` instances to which the given ``tier`` will be
          added. These tiers will be added to the :class:`SiteTierInfo`
          after creation.
        * ``ipns`` should be a list (or ``None`` for an empty list) of
          :class:`PayPalIPN` instances which will be added to the
          :class:`SiteTierInfo` instance after creation.

        """
        tier_changed = tier_changed or datetime.datetime.now()
        tier_info = SiteTierInfo.objects.create(site_id=site_id, tier=tier,
                                                tier_changed=tier_changed,
                                                **kwargs)

        available_tiers = available_tiers or []
        available_tiers.append(tier)
        for tier in available_tiers:
            tier_info.available_tiers.add(tier)

        ipns = ipns or []
        for ipn in ipns:
            tier_info.ipn_set.add(ipn)

        return tier_info
