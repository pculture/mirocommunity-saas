from django.forms.models import modelformset_factory
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.template import defaultfilters

from mirocommunity_saas.models import TierInfo
from mirocommunity_saas import tiers

from localtv.admin.forms import (EditSettingsForm as _EditSettingsForm,
                                 AuthorForm as _AuthorForm)

class EditSettingsForm(_EditSettingsForm):
    def __init__(self, *args, **kwargs):
        _EditSettingsForm.__init__(self, *args, **kwargs)
        tier_info = self.tier_info = TierInfo.objects.get_current()
        if (tier_info.enforce_tiers() and
            not tier_info.get_tier().permit_custom_css()):
            # Uh-oh: custom CSS is not permitted!
            #
            # To handle only letting certain paid users edit CSS,
            # we do two things.
            #
            # 1. Cosmetically, we set the CSS editing box's CSS class
            # to be 'hidden'. (We have some CSS that makes it not show
            # up.)
            css_field = self.fields['css']
            css_field.label += ' (upgrade to enable this form field)'
            css_field.widget.attrs['readonly'] = True
            #
            # 2. In validation, we make sure that changing the CSS is
            # rejected as invalid if the site does not have permission
            # to do that.

    def clean_css(self):
        css = self.cleaned_data.get('css')
        # Does thes SiteSettings permit CSS modifications? If so,
        # return the data the user inputted.
        if (not self.tier_info.enforce_tiers() or
            self.tier_info.get_tier().permit_custom_css()):
            return css # no questions asked

        # We permit the value if it's the same as self.instance has:
        if self.instance.css == css:
            return css

        # Otherwise, reject the change.
        self.data['css'] = self.instance.css
        raise ValidationError(
            "To edit CSS for your site, you have to upgrade.")

class AuthorForm(_AuthorForm):
    def __init__(self, *args, **kwargs):
        _AuthorForm.__init__(self, *args, **kwargs)
        ## Add a note to the 'role' help text indicating how many admins
        ## are permitted with this kind of account.
        tier_info = TierInfo.objects.get_current()
        tier = tier_info.get_tier()
        if tier.admins_limit() is not None:
            message = 'With a %s, you may have %d administrator%s.' % (
                tier_info.get_tier_name_display(),
                tier.admins_limit(),
                defaultfilters.pluralize(tier.admins_limit()))
            self.fields['role'].help_text = message

    def clean_role(self):
        tier_info = TierInfo.objects.get_current()
        tier = tier_info.get_tier()
        if tier_info.enforce_tiers():
            future_role = self.cleaned_data['role']

            looks_good = self._validate_role_with_tiers_enforcement(
                future_role, tier)
            if not looks_good:
                permitted_admins = tier.admins_limit()
                raise ValidationError("You already have %d admin%s in your site. Upgrade to have access to more." % (
                    permitted_admins,
                    defaultfilters.pluralize(permitted_admins)))

        return self.cleaned_data['role']

    def _validate_role_with_tiers_enforcement(self, future_role, tier):
        # If the user tried to create an admin, but the tier does not
        # permit creating another admin, raise an error.
        permitted_admins = tier.admins_limit()

        # Some tiers permit an unbounded number of admins. Then, anything goes.
        if permitted_admins is None:
            return True

        # All non-admin values are permitted
        if future_role !='admin':
            return True

        if self.instance and self.site_settings.user_is_admin(
            self.instance):
            return True # all role values permitted if you're already an admin

        # Okay, so now we know we are trying to make someone an admin in a
        # tier where admins are limited.
        #
        # The question becomes: is there room for one more?
        num_admins = tiers.number_of_admins_including_superuser()
        if (num_admins + 1) <= permitted_admins:
            return True

        # Otherwise, gotta say no.
        return False

AuthorFormSet = modelformset_factory(User,
                                     form=AuthorForm,
                                     can_delete=True,
                                     extra=0)
