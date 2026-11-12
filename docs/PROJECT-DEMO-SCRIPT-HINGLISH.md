# ProofPay AI — 2 minute demo script

“Hello everyone, hamara project hai ProofPay AI—ek payment evidence review platform
jo merchants ko transactions aur supporting documents ek jagah manage karne mein
help karta hai.

Payment dispute ke time invoices, order details aur delivery proofs alag-alag
jagah ho sakte hain. In documents ko manually compare karna time-consuming hota
hai. ProofPay AI isi review process ko organize karta hai.

[Create account / sign in dikhayein]
Merchant apna account create karke login kar sakta hai. Har merchant ka workspace
separate hai, aur documents access karne ke liye authentication required hai.

[Dashboard aur Transactions dikhayein]
Dashboard par transaction count, analyzed cases aur pending review dikhte hain.
Local demo ke liye Start test upload se ek clearly labelled synthetic transaction
open hoti hai. Authorized PayPal Sandbox credentials aur reporting permission
configure hone par Sandbox transactions bhi import ki ja sakti hain.

[Start test upload → Choose file → Upload]
Ab hum synthetic invoice ya delivery record upload karte hain. PDF, PNG, JPEG aur
text supported hain. Upload ke baad Analyze evidence click karte hain. Text parsing
ke saath configured local OCR images aur scanned PDFs se text extract karta hai.

[Findings aur source document kholein]
Existing deterministic analysis pipeline facts ko transaction se compare karti
hai. Amount mismatch ya missing delivery proof jaise issues explanation aur
recommendation ke saath dikhte hain. Available evidence ke liye source document
references bhi milte hain, taaki merchant finding ko check kar sake.

[Response workspace dikhayein]
System supplied evidence ke basis par response draft banata hai. Merchant usse
edit, save aur explicitly approve kar sakta hai. Manual edits par validation warning
show hoti hai. Approval record hoti hai; dispute automatically submit nahi hota.

Technical side par frontend Next.js aur TypeScript mein, backend FastAPI mein,
aur durable data PostgreSQL mein hai. Evidence files private storage mein rehti hain.
Sessions, CSRF checks aur merchant ownership checks data access protect karte hain.

ProofPay AI ka goal merchant ko clear, traceable evidence aur review-ready drafts
dena hai, jisse woh final decision confidence ke saath le sake. Thank you.”

## Demo accuracy notes

- Hosted LLM integration ka claim na karein: current analysis deterministic hai.
- Sandbox connected tabhi bolen jab actual connection check successful ho.
- Synthetic demo transaction ko actual PayPal payment na batayein.
- Approval ka matlab submission nahi hai.
