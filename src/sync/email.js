// SYNC_MODE=email — sends each booking as a calendar invite (iCalendar METHOD:REQUEST) to the
// addresses in INVITE_ADDRESSES (e.g. the Microsoft Bookings calendar mailbox and/or staff),
// and a METHOD:CANCEL when it is cancelled. Needs no IT admin access — just an SMTP account.
//
// With no SMTP_HOST set, the emails are written to data/outbox/*.eml instead (open them in
// Outlook to see exactly what would be sent) — handy for demos.

import fs from 'node:fs';
import path from 'node:path';
import nodemailer from 'nodemailer';
import { inviteIcs, bookingEvent } from '../ics.js';

export function createEmailAdapter({ config, catalog, outboxDir, transport = null }) {
  const { email } = config;
  const smtp =
    transport ||
    (email.host
      ? nodemailer.createTransport({
          host: email.host,
          port: email.port,
          secure: email.port === 465,
          auth: email.user ? { user: email.user, pass: email.pass } : undefined,
        })
      : null);
  // Builds the raw email without sending it (for the outbox).
  const builder = nodemailer.createTransport({ streamTransport: true, buffer: true, newline: 'windows' });
  const icsCtx = { catalog, config };

  async function send(booking, method) {
    if (!email.inviteAddresses.length) {
      throw new Error('INVITE_ADDRESSES is empty — add the Bookings calendar mailbox and/or staff email addresses');
    }
    const organizer = { name: 'Program Bookings', email: email.from };
    const attendees = email.inviteAddresses.map((address) => ({ email: address }));
    const event = bookingEvent(icsCtx, booking);
    const ics = inviteIcs(icsCtx, booking, method, { organizer, attendees });
    const message = {
      from: email.from,
      to: email.inviteAddresses.join(', '),
      subject: method === 'CANCEL' ? `Cancelled: ${event.summary}` : event.summary,
      text: `${method === 'CANCEL' ? 'This booking has been CANCELLED.\n\n' : ''}${event.description}`,
      icalEvent: { method, filename: 'invite.ics', content: ics },
    };

    if (smtp) {
      await smtp.sendMail(message);
      return;
    }
    const info = await builder.sendMail(message);
    fs.mkdirSync(outboxDir, { recursive: true });
    const file = path.join(outboxDir, `${booking.date}_booking-${booking.id}_${method.toLowerCase()}_${Date.now()}.eml`);
    fs.writeFileSync(file, info.message);
  }

  return {
    name: 'email',
    async onBookingCreated(booking) {
      await send(booking, 'REQUEST');
      return {};
    },
    async onBookingCancelled(booking) {
      await send(booking, 'CANCEL');
    },
  };
}
