// frappe.ui.form.on("Scan QR", {
//     // When the button field is clicked
//     scan_qr(frm) {
//         let d = new frappe.ui.Dialog({
//             title: "Scan QR Code",
//             size: "large",
//             fields: [{ fieldtype: "HTML", fieldname: "qr_area" }]
//         });

//         d.show();

//         const qr_div = "qr-reader-" + frappe.utils.get_random(10);
//         d.fields_dict.qr_area.$wrapper.html(`<div id="${qr_div}" style="width:100%; height:400px;"></div>`);

//         setTimeout(() => {
//             const html5QrCode = new Html5Qrcode(qr_div);

//             html5QrCode.start(
//                 { facingMode: "environment" },
//                 { fps: 10, qrbox: 250 },
//                 qrText => {
//                     html5QrCode.stop().then(() => {
//                         d.hide();
//                         console.log("Scanned:", qrText);
//                         process_check_in(frm, qrText);
//                     }).catch(err => console.error("Stop error:", err));
//                 }
//             );
//         }, 300);
//     }
// });

// function process_check_in(frm, qr_value) {
//     frappe.call({
//         method: "buzz.events.doctype.scan_qr.scan_qr.verify_qr",
//         args: { qr: qr_value },
//         callback: (r) => {
//             if (!r.message) {
//                 frappe.msgprint("Invalid QR Code");
//                 print("Invalid QR Code", qr_value);
//                 return;
//             } 

//             let reg = r.message;

//             if (reg.checked_in) {
//                 frappe.msgprint(`⚠ Already Checked-In<br><b>${reg.attendee_name}</b>`);
//             } else {
//                 frappe.call({
//                     method: "buzz.buzz.doctype.scan_qr.scan_qr.mark_checked_in",
//                     args: { name: reg.name },
//                     callback: () => {
//                         frappe.msgprint(`✅ Checked-In: <b>${reg.attendee_name}</b>`);
//                     }
//                 });
//             }
//         }
//     });
// }

frappe.ui.form.on("Scan QR", {
    scan_qr(frm) {
        let d = new frappe.ui.Dialog({
            title: "Scan QR Code",
            size: "large",
            fields: [{ fieldtype: "HTML", fieldname: "qr_area" }]
        });

        d.show();

        const qr_div = "qr-reader-" + frappe.utils.get_random(10);
        d.fields_dict.qr_area.$wrapper.html(`<div id="${qr_div}" style="width:100%; height:400px;"></div>`);
        let scanLock = false;

        setTimeout(() => {
            const html5QrCode = new Html5Qrcode(qr_div);

            // Start continuous scanning
            html5QrCode.start(
                { facingMode: "environment" },
                { fps: 10, qrbox: 250 },
                async (qrText) => {
                    if (scanLock) return; // ignore if another scan is in progress
                    scanLock = true; 
                   
                    // Call server to verify QR
                    let reg = await frappe.call({
                        method: "buzz.buzz.doctype.scan_qr.scan_qr.verify_qr",
                        args: { qr: qrText }
                    }).then(r => r.message);

                    if (!reg) {
                        frappe.show_alert({ message: "Invalid QR Code", indicator: "red" });
                        scanLock = false; // unlock immediately for next scan
                        return;
                      
                    }

                    if (reg.checked_in) {
                        frappe.show_alert({ message: ` Already Checked-In: ${reg.attendee_name}`, indicator: "orange" });
                        scanLock = false; // unlock for next scan
                    } else {
                        await frappe.call({
                            method: "buzz.buzz.doctype.scan_qr.scan_qr.mark_checked_in",
                            args: { name: reg.name }
                        });
                        frappe.show_alert({ message: ` Checked-In: ${reg.attendee_name}`, indicator: "green" });
                        setTimeout(() => { scanLock = false; }, 1500); // 1500ms delay
                    }
                },
                (err) => {
                    // optional: handle scanning errors
                    // console.warn("Scan error:", err);
                }
            ).catch(err => console.error("Start error:", err));

            // Optional: add a Close button inside dialog
            d.set_primary_action("Close", () => {
                html5QrCode.stop().then(() => d.hide());
            });

        }, 300);
    }
});

