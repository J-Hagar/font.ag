/**
 * Beta Epsilon member and public inquiry router.
 * Server requests must carry the shared secret saved in script properties.
 * No website visitor receives direct access to private Sheets or Gmail.
 */
var SHEET_ID = '1smGK3171vIcxUT93Qn9PestvwjZeupwH083qFI_NlUs';
var MEMBER_PURPOSE = 'Member Account Request';
var PUBLIC_PURPOSES = ['Interested in Joining', 'Learn More About AGR',
  'General Inquiry', 'Alumni Relations', 'Chapter History or Photos'];
function authorize() {
  var ss = SpreadsheetApp.openById(SHEET_ID);
  return ss.getSheets().length + ':' + MailApp.getRemainingDailyQuota();
}
function checkAuthorization() {
  var info = ScriptApp.getAuthorizationInfo(ScriptApp.AuthMode.FULL);
  return String(info.getAuthorizationStatus());
}
function respond(data) {
  return ContentService.createTextOutput(JSON.stringify(data)).setMimeType(ContentService.MimeType.JSON);
}
function safeCell(value) {
  var text = String(value || '');
  return '=+-@'.indexOf(text.charAt(0)) === -1 ? text : "'" + text;
}
function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) throw Error('Missing POST body');
    var data = JSON.parse(e.postData.contents);
    var secret = PropertiesService.getScriptProperties().getProperty('ROUTER_SHARED_SECRET');
    if (!secret || secret !== data.routerSecret) throw Error('Access denied');
    var purpose = String(data.purpose || '').trim();
    var name = String(data.name || '').trim();
    var email = String(data.email || '').trim().toLowerCase();
    var address = String(data.address || '').trim();
    var phone = String(data.phone || '').trim();
    var studNumber = String(data.studNumber || '').trim();
    var affiliation = String(data.affiliation || '').trim();
    var message = String(data.message || '').trim();
    if (!name || !email.includes('@') || !email.includes('.')) throw Error('Invalid name or email');
    if (purpose === MEMBER_PURPOSE) {
      if (!address || !phone || !studNumber) throw Error('Missing member fields');
      if (['undergraduate','alumni'].indexOf(affiliation) === -1) throw Error('Invalid affiliation');
    } else {
      if (PUBLIC_PURPOSES.indexOf(purpose) === -1) throw Error('Invalid purpose');
      if (!message) throw Error('Missing inquiry');
    }
    var id = String(data.submissionId || Utilities.getUuid());
    var lock = LockService.getScriptLock();
    lock.waitLock(15000);
    try {
      var ss = SpreadsheetApp.openById(SHEET_ID);
      if (purpose === MEMBER_PURPOSE) {
        var memberSheet = ss.getSheetByName('Member Access Requests');
        if (!memberSheet) throw Error('Missing member tab');
        if (!memberSheet.createTextFinder(id).matchEntireCell(true).findNext()) {
          memberSheet.appendRow([new Date().toISOString(), id, safeCell(name), safeCell(email),
            safeCell(address), safeCell(phone), 'Pending Notification', '', safeCell(studNumber), safeCell(affiliation)]);
        }
        var found = memberSheet.createTextFinder(id).matchEntireCell(true).findNext();
        if (!found) throw Error('Failed to save member request');
        var row = found.getRow();
        var status = memberSheet.getRange(row, 7).getDisplayValue();
        if (status !== 'New') {
          MailApp.sendEmail({
            to: 'asuagrbe@gmail.com',
            subject: 'Beta Epsilon member account request - ' + name,
            body: 'New member account request.\nName: ' + name + '\nEmail: ' + email +
              '\nAddress: ' + address + '\nPhone: ' + phone +
              '\nStatus: ' + affiliation + '\nRequest ID: ' + id +
              '\nReview the private Member Access Requests sheet for Stud Number (PIN).',
            replyTo: email
          });
          memberSheet.getRange(row, 7).setValue('New');
        }
        return respond({status:'submitted',route:'member-sheet-and-email',submissionId:id});
      }
      var publicSheet = ss.getSheetByName('Sheet1');
      if (!publicSheet) throw Error('Missing public tab');
      if (!publicSheet.createTextFinder(id).matchEntireCell(true).findNext()) {
        publicSheet.appendRow([new Date().toISOString(), id, safeCell(purpose), safeCell(name),
          safeCell(email), safeCell(message), 'Public website', 'New', '']);
      }
      return respond({status:'submitted',route:'public-sheet-only',submissionId:id});
    } finally {
      lock.releaseLock();
    }
  } catch (err) {
    console.error('Routing failed: ' + String(err));
    return respond({status:'error',message:'Submission not confirmed'});
  }
}
