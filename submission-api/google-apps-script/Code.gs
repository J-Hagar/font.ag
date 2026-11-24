/** AGR Beta Epsilon public website inquiry router (owned by ASUAGRBE@gmail.com).
 *  Server-to-server only. Web app must execute as this account. Never embed shared secret in website JS.
 *  Project Settings > Script Properties: ROUTER_SHARED_SECRET = secret configured in Render.
 */
const SHEET_ID = '1smGK3171vIcxUT93Qn9PestvwjZeupwH083qFI_NlUs';
const CHAPTER_INBOX = 'asuagrbe@gmail.com';
const RECRUITMENT = ['Interested in Joining', 'Learn More About AGR'];
const ADMIN_ONLY = ['General Inquiry', 'Alumni Relations', 'Chapter History or Photos'];

function authorize() {
  const name = SpreadsheetApp.openById(SHEET_ID).getSheets()[0].getName();
  const quota = MailApp.getRemainingDailyQuota();
  return 'Authorized sheet ' + name + ', available email quota ' + quota;
}

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents || e.postData.contents.length > 14000)
      throw new Error('Invalid request');
    const p = JSON.parse(e.postData.contents);
    const sharedSecret = PropertiesService.getScriptProperties().getProperty('ROUTER_SHARED_SECRET');
    if (!sharedSecret || p.routerSecret !== sharedSecret)
      throw new Error('Not authorized');
    const purpose = String(p.purpose || '').trim();
    const name = String(p.name || '').trim().slice(0, 150);
    const email = String(p.email || '').trim().toLowerCase().slice(0, 254);
    const message = String(p.message || '').trim().slice(0, 4000);
    if (!RECRUITMENT.includes(purpose) && !ADMIN_ONLY.includes(purpose))
      throw new Error('Invalid purpose');
    if (name.length < 2 || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) || message.length < 5)
      throw new Error('Invalid required fields');

    const id = Utilities.getUuid();
    const timestamp = new Date().toISOString();
    if (RECRUITMENT.includes(purpose)) {
      const safe = value => /^[=+\-@]/.test(value.trimStart()) ? "'" + value : value;
      const lock = LockService.getScriptLock();
      if (!lock.tryLock(10000)) throw new Error('Server busy');
      try {
        const sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName('Sheet1');
        if (!sheet) throw new Error('Missing Sheet1');
        sheet.appendRow([timestamp, id, purpose, safe(name), safe(email), safe(message),
          'https://agr-beta-epsilon-design-test.onrender.com', 'New', '']);
      } finally {
        lock.releaseLock();
      }
      return jsonOutput({status: 'saved', route: 'recruitment', submissionId: id});
    }

    MailApp.sendEmail({
      to: CHAPTER_INBOX,
      subject: 'AGR Beta Epsilon website inquiry: ' + purpose,
      body: 'New website inquiry\n\nPurpose: ' + purpose +
        '\nName: ' + name + '\nReply to: ' + email +
        '\nReceived: ' + timestamp + '\nReference: ' + id +
        '\n\nMessage:\n' + message,
      name: 'AGR Beta Epsilon Website',
      replyTo: email
    });
    return jsonOutput({status: 'emailed', route: 'chapter-inbox', submissionId: id});
  } catch (err) {
    console.error(String(err));
    return jsonOutput({status: 'error', message: 'Unable to process inquiry'});
  }
}

function jsonOutput(data) {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
