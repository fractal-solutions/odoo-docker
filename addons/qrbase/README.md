# QR Base

QR Base is an Odoo app for creating, tracking, and managing QR-code driven customer acquisition.

It is designed for teams that need to know where a lead or customer came from, whether that source was:

- a partner referral
- an event or show
- a website campaign
- a point of sale location
- a CRM pipeline initiative
- any other custom allocation

## What It Does

- Creates unique QR codes with purpose and source metadata
- Gives each QR code a public landing page
- Logs scans and captures visitor details
- Creates or updates CRM leads from scan submissions
- Stores QR attribution on the customer profile
- Tracks consent, duplicate contacts, and automatic prospect/customer outcomes
- Supports campaign-level and QR-level analytics with graph and pivot views
- Generates reports with filtering and export options
- Marks customers automatically when sales or POS orders are confirmed
- Provides a daily lapsed-customer automation hook

## Core Workflow

1. Create a QR campaign.
2. Add one or more QR codes to that campaign.
3. Print or share the generated QR code.
4. When someone scans it, the landing page records the visit.
5. If the visitor submits details, the module links the scan to a contact and lead.
6. If the scan results in a purchase, the contact is promoted to customer.
7. If the customer becomes inactive for long enough, the cron can mark them as lapsed.

## Data Model

- `qrbase.campaign` holds the business grouping, allocation type, and campaign purpose.
- `qrbase.code` holds each unique QR code, its token, and its public landing URL.
- `qrbase.scan` stores every scan event and visitor submission.
- `qrbase.report.wizard` drives parameterized reporting and CSV/PDF export.
- `res.partner` is extended with lifecycle and attribution fields.
- `crm.lead` is extended with QR source links.

## Installation Notes

The module is an application and appears in Odoo with its own icon.
It depends on:

- `base`
- `crm`
- `contacts`
- `website`
- `sale_management`
- `point_of_sale`

## Admin View

The backend menu exposes:

- QR campaigns
- QR codes
- scan logs
- analytics dashboards
- report exports

The public landing page includes a branded QR scan experience with a logo and lead capture form.

## Notes

This module is structured to fit Odoo's CRM workflow, but the exact customer/prospect rules
can still be refined to match your team's internal definitions.
When you upgrade after code changes, use the Apps upgrade action or run `odoo -u qrbase -d <database> --stop-after-init`.
