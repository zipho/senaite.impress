# -*- coding: utf-8 -*-
#
# This file is part of SENAITE.PUBLISHER
#
# Copyright 2018 by it's authors.

from bika.lims import api
from bika.lims import bikaMessageFactory as _
from bika.lims import logger
from bika.lims.browser.bika_listing import BikaListingView
from bika.lims.utils import to_utf8
from Products.CMFPlone.utils import safe_unicode
from ZODB.POSException import POSKeyError


class PublishedResults(BikaListingView):
    """View of all published results for this client
    """

    def __init__(self, context, request):
        super(PublishedResults, self).__init__(context, request)

        self.catalog = "portal_catalog"
        self.contentFilter = {
            "portal_type": "ARReport",
            "path": {
                "query": api.get_path(self.context),
                "depth": 2,
            },
            "sort_on": "created",
            "sort_order": "descending",
        }

        self.form_id = "published_results"
        self.title = _("Published results")

        self.icon = "{}/{}".format(
            self.portal_url,
            "++resource++bika.lims.images/report_big.png"
        )
        self.context_actions = {}

        self.allow_edit = False
        self.show_select_column = True
        self.show_workflow_action_buttons = True
        self.pagesize = 30

        send_email_transition = {
            "id": "send_email",
            "title": _("Send Email"),
            "url": "send_email"
        }

        self.columns = {
            "AnalysisRequest": {"title": _("Analysis Request")},
            "State": {"title": _("Review State")},
            "PDF": {"title": _("Download")},
            "FileSize": {"title": _("Size")},
            "Date": {"title": _("Published Date")},
            "PublishedBy": {"title": _("Published By")},
            "Recipients": {"title": _("Recipients")},
        }

        self.review_states = [
            {
                "id": "default",
                "title": "All",
                "contentFilter": {},
                "columns": [
                    "AnalysisRequest",
                    "State",
                    "PDF",
                    "FileSize",
                    "Date",
                    "PublishedBy",
                    "Recipients",
                ],
                "custom_transitions": [send_email_transition]
            },
        ]

    def before_render(self):
        """Before render hook
        """
        logger.info("PublishedResults.before_render")

    def get_filesize(self, pdf):
        """Compute the filesize of the PDF
        """
        try:
            filesize = float(pdf.get_size())
            return filesize / 1024
        except (POSKeyError, TypeError):
            return 0

    def localize_date(self, date):
        """Return the localized date
        """
        return self.ulocalized_time(date, long_format=1)

    def folderitem(self, obj, item, index):
        """Augment folder listing item
        """
        pdf = obj.getPdf()
        ar = obj.getAnalysisRequest()
        review_state = api.get_workflow_status_of(ar)
        status_title = review_state.capitalize().replace("_", " ")

        item["replace"]["AnalysisRequest"] = "<a href='{}'>{}</a>".format(
            ar.absolute_url(), ar.Title()
        )
        filesize = self.get_filesize(pdf)
        if filesize > 0:
            anchor = "<a href='{}/download'>{}</a>".format(
                obj.absolute_url(), "PDF")
            item["replace"]["PDF"] = anchor
        item["State"] = _(status_title)
        item["state_class"] = "state-{}".format(review_state)
        item["FileSize"] = "{:.2f} Kb".format(filesize)
        fmt_date = self.localize_date(obj.created())
        item["Date"] = fmt_date
        item["PublishedBy"] = self.user_fullname(obj.Creator())

        # N.B. There is a bug in the current publication machinery, so that
        # only the primary contact get stored in the Attachment as recipient.
        #
        # However, we're interested to show here the full list of recipients,
        # so we use the recipients of the containing AR instead.
        recipients = []

        for recipient in self.get_recipients(ar):
            email = safe_unicode(recipient["EmailAddress"])
            fullname = safe_unicode(recipient["Fullname"])
            if email:
                value = u"<a href='mailto:{}'>{}</a>".format(email, fullname)
                recipients.append(value)

        item["replace"]["Recipients"] = ", ".join(recipients)

        # No recipient with email set preference found in the AR, so we also
        # flush the Recipients data from the Attachment
        if not recipients:
            item["Recipients"] = ""

        return item

    def get_recipients(self, ar):
        """Return the AR recipients in the same format like the AR Report
        expects in the records field `Recipients`
        """
        plone_utils = api.get_tool("plone_utils")

        def is_email(email):
            if not plone_utils.validateSingleEmailAddress(email):
                return False
            return True

        def recipient_from_contact(contact):
            if not contact:
                return None
            email = contact.getEmailAddress()
            if not is_email(email):
                return None
            return {
                "UID": api.get_uid(contact),
                "Username": contact.getUsername(),
                "Fullname": to_utf8(contact.Title()),
                "EmailAddress": email,
                "PublicationModes": contact.getPublicationPreference(),
            }

        def recipient_from_email(email):
            if not is_email(email):
                return None
            return {
                "UID": "",
                "Username": "",
                "Fullname": email,
                "EmailAddress": email,
                "PublicationModes": ("email", "pdf",),
            }

        # Primary Contacts
        to = filter(None, [recipient_from_contact(ar.getContact())])
        # CC Contacts
        cc = filter(None, map(recipient_from_contact, ar.getCCContact()))
        # CC Emails
        cc_emails = map(lambda x: x.strip(), ar.getCCEmails().split(","))
        cc_emails = filter(None, map(recipient_from_email, cc_emails))

        return to + cc + cc_emails