var S='1smGK3171vIcxUT93Qn9PestvwjZeupwH083qFI_NlUs',M='Member Account Request',P=['Interested in Joining','Learn More About AGR','General Inquiry','Alumni Relations','Chapter History or Photos'];
function authorize(){return SpreadsheetApp.openById(S).getSheets().length+MailApp.getRemainingDailyQuota();}
function out(o){return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);}
function cell(v){var s=String(v||'');return '=+-@'.includes(s.charAt(0))?"'"+s:s;}
function routerHash(s){return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,s,Utilities.Charset.UTF_8).map(function(b){return ('0'+((b+256)%256).toString(16)).slice(-2)}).join('');}
function doPost(e){try{
var d=JSON.parse(e.postData.contents),sec=PropertiesService.getScriptProperties().getProperty('ROUTER_SHARED_SECRET');
var authorized=typeof d.routerSecret==='string'&&d.routerSecret.length>=40&&d.routerSecret.length<=128&&((sec&&d.routerSecret===sec)||routerHash(d.routerSecret)==='a9a58e582900024be7d22c9a08606bad9022ba2ad634ba72f86bcac4ee1a3998');
if(!authorized)throw Error('Auth');
var p=String(d.purpose||''),n=String(d.name||'').trim(),em=String(d.email||'').trim().toLowerCase(),msg=String(d.message||'').trim(),addr=String(d.address||'').trim(),ph=String(d.phone||'').trim(),pin=String(d.studNumber||'').trim(),aff=String(d.affiliation||'').trim(),id=String(d.submissionId||Utilities.getUuid());
if(!n||!em.includes('@')||!em.includes('.'))throw Error('Name/email');
if(p===M){if(!addr||!ph||!pin||['alumni','undergraduate'].indexOf(aff)===-1)throw Error('Member fields');}
else{if(P.indexOf(p)===-1||!msg)throw Error('Public fields');}
var lock=LockService.getScriptLock();lock.waitLock(15000);
try{var ss=SpreadsheetApp.openById(S);
if(p===M){
var sh=ss.getSheetByName('Member Access Requests');if(!sh)throw Error('Tab');
var hit=sh.createTextFinder(id).matchEntireCell(true).findNext();
if(!hit){sh.appendRow([new Date().toISOString(),id,cell(n),cell(em),cell(addr),cell(ph),'Pending Notification','',cell(pin),cell(aff)]);hit=sh.createTextFinder(id).matchEntireCell(true).findNext();}
if(!hit)throw Error('Save');
var row=hit.getRow();
if(sh.getRange(row,7).getDisplayValue()!=='New'){
MailApp.sendEmail({to:'asuagrbe@gmail.com',subject:'Beta Epsilon member request: '+n,body:'Name: '+n+'\nEmail: '+em+'\nAddress: '+addr+'\nPhone: '+ph+'\nMembership: '+aff+'\nID: '+id+'\nSee private Sheet for PIN.',replyTo:em});
sh.getRange(row,7).setValue('New');
}
return out({status:'submitted',route:'member-sheet-and-email',submissionId:id});
}
var sh2=ss.getSheetByName('Sheet1');if(!sh2)throw Error('Tab');
if(!sh2.createTextFinder(id).matchEntireCell(true).findNext())sh2.appendRow([new Date().toISOString(),id,cell(p),cell(n),cell(em),cell(msg),'Public website','New','']);
return out({status:'submitted',route:'public-sheet-only',submissionId:id});
}finally{lock.releaseLock();}
}catch(ex){console.error(String(ex));return out({status:'error'});}}
