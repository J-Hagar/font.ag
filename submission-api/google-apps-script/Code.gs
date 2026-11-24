/**
 * AGR Beta Epsilon chapter website inquiry routing.
 * Deploy as chapter account ASUAGRBE@gmail.com, execute as Me.
 * Set Script Property ROUTER_SHARED_SECRET to match the Render server.
 * Only server-side Render may supply the secret. Never put it in public HTML/JS.
 */
const SHEET_ID = '1smGK3171vIcxUT93Qn9PestvwjZeupwH083qFI_NlUs';
const CHAPTER_INBOX = 'asuagrbe@gmail.com';
const PUBLIC_PURPOSES = [
  'Interested in Joining',
  'Learn More About AGR',
  'General Inquiry',
  'Alumni Relations',
  'Chapter History or Photos'
];
const MEMBER_PURPOSE = 'Member Account Request';

function authorize() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  return 'Sheets available: ' + ss.getSheets().map(s => s.getName()).join(', ') +
    '; email quota: ' + MailApp.getRemainingDailyQuota();
}

function output(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents || e.postData.contents.length > 14000)
      throw new Error('Invalid request');
    const data = JSON.parse(e.postData.contents);
    const secret = PropertiesService.getScriptProperties().getProperty('ROUTER_SHARED_SECRET');
    if (!secret || data.routerSecret !== secret) throw new Error('Not authorized');

    const purpose = String(data.purpose || '').trim();
    const name = String(data.name || '').trim().slice(0, 150);
    const email = String(data.email || '').trim().toLowerCase().slice(0, 254);
    const message = String(data.message || '').trim().slice(0, 4000);
    const address = String(data.address || '').trim().slice(0, 400);
    const phone = String(data.phone || '').trim().slice(0, 40);
    const studNumber = String(data.studNumber || '').trim().slice(0, 64);
    if (name.length < 2 || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email))
      throw new Error('Invalid name or email');
    if (purpose !== MEMBER_PURPOSE && PUBLIC_PURPOSES.indexOf(purpose) < 0)
      throw new Error('Invalid purpose');
    if (purpose === MEMBER_PURPOSE && (address.length < 8 || !/^[0-9+(). \-]{7,40}$/.test(phone) || !studNumber))
      throw new Error('Missing address, phone or Stud Number (PIN)');
    if (purpose !== MEMBER_PURPOSE && message.length < 5)
      throw new Error('Missing message');

    const id = String(data.submissionId || Utilities.getUuid()).slice(0, 100);
    const timestamp = new Date().toISOString();
    const safe = value => /^[=+\-@]/.test(value.trimStart()) ? "'" + value : value;
    const lock = LockService.getScriptLock();
    if (!lock.tryLock(12000)) throw new Error('Busy');
    try {
      const ss = SpreadsheetApp.openById(SHEET_ID);
      if (purpose === MEMBER_PURPOSE) {
        const sheet = ss.getSheetByName('Member Access Requests');
        if (!sheet) throw new Error('Member requests sheet missing');
        // Avoid duplicate entries for repeated retries of the same submission ID.
        if (sheet.createTextFinder(id).matchEntireCell(true).findNext() === null) {
          sheet.appendRow([timestamp, id, safe(name), safe(email), safe(address), safe(phone), 'New', '', safe(studNumber)]);
        }
      } else {
        const sheet = ss.getSheetByName('Sheet1');
        if (!sheet) throw new Error('Public inquiry sheet missing');
        if (sheet.createTextFinder(id).matchEntireCell(true).findNext() === null) {
          sheet.appendRow([timestamp, id, purpose, safe(name), safe(email), safe(message),
            'https://agr-beta-epsilon-design-test.onrender.com', 'New', '']);
        }
      }
    } finally {
      lock.releaseLock();
    }

    if (purpose === MEMBER_PURPOSE) {
      MailApp.sendEmail({
        to: CHAPTER_INBOX,
        subject: 'Beta Epsilon member account request: ' + name,
        body: 'New member account request — approval required.\n\n' +
          'Name: ' + name + '\nEmail: ' + email + '\nMailing address: ' + address +
          '\nPhone: ' + phone + '\nRequest ID: ' + id +
          '\n\nSee the private Member Access Requests Google Sheet tab. ' +
          'Verify chapter membership independently before creating or approving portal access.',
        replyTo: email,
        name: 'AGR Beta Epsilon Website'
      });
      return output({status: 'submitted', route: 'member-sheet-and-email', submissionId: id});
    }

    return output({status: 'submitted', route: 'public-sheet-only', submissionId: id});
  } catch (err) {
    console.error('Inquiry failed: ' + String(err));
    return output({status: 'error', message: 'Inquiry not confirmed'});
  }
}
