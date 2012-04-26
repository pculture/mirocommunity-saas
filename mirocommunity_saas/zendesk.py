# Miro Community - Easiest way to make a video website
#
# Copyright (C) 2011, 2012 Participatory Culture Foundation
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

### FIXME
# This file should get moved out into its own Python package.
###

import httplib2
from xml.dom.minidom import Document

from django.conf import settings

def generate_ticket_body(subject_text, body_text, requester_email_text,
                         use_configured_assignee=True):
    doc = Document()
    # Create the outer ticket element
    ticket = doc.createElement("ticket")
    doc.appendChild(ticket)

    # Create the other data
    subject = doc.createElement('subject')
    subject.appendChild(doc.createTextNode(subject_text))
    ticket.appendChild(subject)

    requester = doc.createElement('requester-email')
    requester.appendChild(doc.createTextNode(requester_email_text))
    ticket.appendChild(requester)

    requester = doc.createElement('group-id')
    requester.appendChild(doc.createTextNode('86020'))
    ticket.appendChild(requester)

    if (use_configured_assignee and
        getattr(settings, "ZENDESK_ASSIGN_TO_USER_ID", None)):
        value = getattr(settings, "ZENDESK_ASSIGN_TO_USER_ID")
        assignee = doc.createElement('assignee-id')
        assignee.appendChild(doc.createTextNode(unicode(value)))
        ticket.appendChild(assignee)

    description = doc.createElement('description')
    description.appendChild(doc.createTextNode(body_text))
    ticket.appendChild(description)

    return doc.toxml()

outbox = []

def create_ticket(subject, body, use_configured_assignee,
                  requester_email='paulproteus+robot@pculture.org'):
    global outbox

    # Prepare kwargs for HTTP request
    ticket_body_kwargs = {'subject': subject, 'body': body, 'requester_email': requester_email}
    
    # If we are inside the test suite, just create an "outbox" and push things onto it
    # Detect the test suite by looking at the email backend
    if settings.EMAIL_BACKEND == 'django.core.mail.backends.locmem.EmailBackend':
        outbox.append(ticket_body_kwargs)
        return True
    
    h= httplib2.Http("/tmp/.cache")
    username = getattr(settings, "ZENDESK_USERNAME", None)
    password = getattr(settings, "ZENDESK_PASSWORD", None)
    if username and password:
        h.add_credentials(username, password)
    else:
        raise ValueError, "Cannot create ticket because Zendesk not configured. Bailing out now."

    http_data = dict(headers={'Content-Type': 'application/xml'},
                     body=(
            generate_ticket_body(
                subject_text=subject, body_text=body,
                requester_email_text=requester_email,
                use_configured_assignee=use_configured_assignee)))


    # Oh, so we're in real mode? Okay, then let's actually do the HTTP game.
    response = h.request("http://mirocommunity.zendesk.com/tickets.xml", "POST", **http_data)
    if response[0]['status'] == '201':
        return True
    return False
