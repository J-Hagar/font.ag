(function(){const toggle=document.getElementById('navToggle');const nav=document.getElementById('mainNav');const groups=[...document.querySelectorAll('.nav-dropdown')];toggle.addEventListener('click',()=>{const active=nav.classList.toggle('is-open');toggle.setAttribute('aria-expanded',String(active))});groups.forEach(group=>{const btn=group.querySelector('button');btn.addEventListener('click',()=>{const open=group.classList.contains('open');groups.forEach(item=>{item.classList.remove('open');item.querySelector('button').setAttribute('aria-expanded','false')});group.classList.toggle('open',!open);btn.setAttribute('aria-expanded',String(!open))})});document.addEventListener('click',event=>{if(!event.target.closest('.nav-dropdown'))groups.forEach(g=>{g.classList.remove('open');g.querySelector('button').setAttribute('aria-expanded','false')})});document.addEventListener('keydown',event=>{if(event.key==='Escape')groups.forEach(g=>{g.classList.remove('open');g.querySelector('button').setAttribute('aria-expanded','false')})});document.getElementById('year').textContent=String(new Date().getFullYear())})();

(function(){
const form=document.getElementById('chapterContactForm');
if(!form) return;
form.addEventListener('submit',function(event){
 event.preventDefault();
 if(!form.reportValidity()) return;
 const purpose=document.getElementById('inquiryPurpose').value;
 const name=document.getElementById('contactName').value.trim();
 const email=document.getElementById('contactEmail').value.trim();
 const message=document.getElementById('contactMessage').value.trim();
 const status=document.getElementById('contactFormStatus');
 if(!purpose||!name||!email||!message){status.textContent='Please complete all required fields.';return;}
 const subject='Beta Epsilon Website Inquiry — '+purpose;
 const body='Inquiry type: '+purpose+'\nFrom: '+name+'\nReply-to email: '+email+'\n\nMessage:\n'+message+'\n\nSent from the Beta Epsilon website inquiry form.';
 const prepared=subject+'\n\n'+body;
 const chapterMailbox=''; // Enable only when the chapter Gmail account is confirmed active.
 const page='';
 if(chapterMailbox){window.location.href='mailto:'+encodeURIComponent(chapterMailbox)+'?subject='+encodeURIComponent(subject)+'&body='+encodeURIComponent(body);status.textContent='Your email application has been opened. Review and send the message.';return;}
 status.textContent='The chapter mailbox is still being created. Your draft appears below; it has NOT been sent or saved. Please retain it until the mailbox is activated.';
 showPrepared(prepared,status);
 function showPrepared(text,container){let preview=document.getElementById('preparedContactMessage');if(!preview){preview=document.createElement('textarea');preview.id='preparedContactMessage';preview.rows=9;preview.readOnly=true;container.after(preview);}preview.value=text;preview.focus();}
});
})();
