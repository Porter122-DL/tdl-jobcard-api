// ==============================================================
// DesignLab — Fill Job Card (cloud edition)
// File > Scripts > Fill Job Card
//
// Fills the job card on the current file using Shopify order data
// fetched from the Vercel serverless endpoint. No local Python needed.
//
// ONE thing you (or IT) needs to edit before distributing:
//   ENDPOINT_URL — set to your Vercel deployment URL
// ==============================================================

#target illustrator

(function () {
    // ------- EDIT THIS ONE LINE -------
    var ENDPOINT_URL = "https://tdl-jobcard-api-beta.vercel.app/api/order/";
    // If your Vercel deploy uses a shared secret, append it here:
    //   var API_KEY = "?key=YOUR_SECRET";
    var API_KEY = "";
    // ----------------------------------

    var CONFIG_DIR = Folder.userData + "/DesignLab";
    var CONFIG_PATH = CONFIG_DIR + "/config.json";

    var CHECKBOXES = [
        "CHK_INSTALL",
        "CHK_FORK",
        "CHK_FORK_NEW_SHOWA",
        "CHK_FORK_SHOWA",
        "CHK_FORK_WP",
        "CHK_FORK_KYB",
        "CHK_CLEAR_SWINGARMS",
        "CHK_GUTS_SEAT",
        "CHK_MINI_PLATES"
    ];

    // ---------- tiny JSON escape ----------
    function jsonEscape(s) {
        return String(s)
            .replace(/\\/g, "\\\\")
            .replace(/"/g, '\\"')
            .replace(/\n/g, "\\n")
            .replace(/\r/g, "\\r")
            .replace(/\t/g, "\\t");
    }

    // ---------- config (initials only; token lives on Vercel) ----------
    function readConfig() {
        var f = new File(CONFIG_PATH);
        if (!f.exists) return {};
        f.encoding = "UTF-8";
        f.open("r");
        var content = f.read();
        f.close();
        if (typeof JSON !== "undefined") {
            try { return JSON.parse(content); } catch (e) {}
        }
        try { return eval("(" + content + ")"); } catch (e) { return {}; }
    }

    function writeConfig(cfg) {
        var folder = new Folder(CONFIG_DIR);
        if (!folder.exists) folder.create();
        var initials = cfg.designer_initials || "";
        var body = '{\n  "designer_initials": "' + jsonEscape(initials) + '"\n}\n';
        var f = new File(CONFIG_PATH);
        f.encoding = "UTF-8";
        f.open("w");
        f.write(body);
        f.close();
    }

    function ensureInitials() {
        var cfg = readConfig();
        if (!cfg.designer_initials) {
            var input = prompt(
                "Enter your designer initials (e.g. NP, MF).\n\nThis only needs to be set once per machine.",
                ""
            );
            if (!input) return null;
            cfg.designer_initials = input.replace(/\s/g, "").toUpperCase();
            writeConfig(cfg);
        }
        return cfg.designer_initials;
    }

    // ---------- HTTP via curl (works in Illustrator 2024+) ----------
    function tryParse(text) {
        if (typeof JSON !== "undefined") {
            try { return JSON.parse(text); } catch (e) {}
        }
        try { return eval("(" + text + ")"); } catch (e) {}
        return null;
    }

    function httpGet(fullUrl) {
        var isWin = ($.os.indexOf("Windows") !== -1);
        var stamp = (new Date()).getTime();
        var tempDir = Folder.temp;

        var outFile = new File(tempDir + "/dlab_out_" + stamp + ".json");
        var doneFile = new File(tempDir + "/dlab_done_" + stamp + ".flag");
        var scriptFile;

        try { if (outFile.exists) outFile.remove(); } catch (e) {}
        try { if (doneFile.exists) doneFile.remove(); } catch (e) {}

        if (isWin) {
            scriptFile = new File(tempDir + "/dlab_run_" + stamp + ".bat");
            scriptFile.encoding = "UTF-8";
            scriptFile.open("w");
            scriptFile.writeln("@echo off");
            scriptFile.writeln('curl.exe -sL "' + fullUrl + '" -o "' + outFile.fsName + '"');
            scriptFile.writeln('echo done > "' + doneFile.fsName + '"');
            scriptFile.close();
        } else {
            scriptFile = new File(tempDir + "/dlab_run_" + stamp + ".command");
            scriptFile.encoding = "UTF-8";
            scriptFile.open("w");
            scriptFile.writeln("#!/bin/sh");
            scriptFile.writeln('/usr/bin/curl -sL "' + fullUrl + '" -o "' + outFile.fsName + '"');
            scriptFile.writeln('echo done > "' + doneFile.fsName + '"');
            scriptFile.close();
        }

        scriptFile.execute();

        var maxIters = 120; // up to 30s
        while (maxIters-- > 0) {
            $.sleep(250);
            if (doneFile.exists) break;
        }
        if (!doneFile.exists) {
            return { error: "Request timed out reaching " + fullUrl + ". Check internet / endpoint URL." };
        }
        if (!outFile.exists) {
            return { error: "curl finished with no output. Try opening " + fullUrl + " in a browser." };
        }

        outFile.encoding = "UTF-8";
        outFile.open("r");
        var content = outFile.read();
        outFile.close();
        try { outFile.remove(); } catch (e) {}
        try { doneFile.remove(); } catch (e) {}
        try { scriptFile.remove(); } catch (e) {}

        if (!content) return { error: "Empty response from endpoint." };
        var parsed = tryParse(content);
        if (parsed === null) {
            return { error: "Could not parse response: " + content.substring(0, 300) };
        }
        return parsed;
    }

    // ---------- DOM traversal ----------
    function walkItems(container, cb) {
        var i;
        if (container.pageItems) {
            for (i = 0; i < container.pageItems.length; i++) {
                cb(container.pageItems[i]);
                walkItems(container.pageItems[i], cb);
            }
        }
        if (container.layers) {
            for (i = 0; i < container.layers.length; i++) {
                cb(container.layers[i]);
                walkItems(container.layers[i], cb);
            }
        }
    }

    function findByName(doc, name) {
        var results = [];
        walkItems(doc, function (item) {
            if (item.name === name) results.push(item);
        });
        return results;
    }

    function setText(doc, name, value) {
        var items = findByName(doc, name);
        for (var i = 0; i < items.length; i++) {
            if (items[i].typename === "TextFrame") {
                items[i].contents = value == null ? "" : String(value);
            }
        }
        return items.length;
    }

    function setCheckbox(doc, name, checked) {
        var items = findByName(doc, name);
        for (var i = 0; i < items.length; i++) {
            try { items[i].hidden = !checked; } catch (e) {}
        }
        return items.length;
    }

    // ---------- Main ----------
    if (app.documents.length === 0) {
        alert("Open the proof file with the job card template before running this script.");
        return;
    }
    var doc = app.activeDocument;

    var initials = ensureInitials();
    if (!initials) return;

    var orderInput = prompt("Enter Shopify order number:", "");
    if (!orderInput) return;
    var orderNum = orderInput.replace(/^#/, "").replace(/\s/g, "");
    if (!/^\d+$/.test(orderNum)) {
        alert("Order number must be digits only.");
        return;
    }

    var order = httpGet(ENDPOINT_URL + orderNum + API_KEY);
    if (order.error) {
        alert("Job Card Fill failed:\n\n" + order.error);
        return;
    }

    var bike = order.bike || "";
    if (!bike) {
        bike = prompt("Bike model wasn't in the Shopify order. Type it now:", "") || "";
    }

    var missingFrames = [];
    var frameMap = {
        "SHOPIFY_NUM": order.shopify_num,
        "CUSTOMER_NAME": order.customer_name,
        "BIKE": bike,
        "DESIGNER": initials,
        "NOTES": order.notes,
        "BASE_MEDIA": order.base_media,
        "LAMINATE": order.laminate,
        "PLASTICS_BRAND": order.plastics_brand,
        "MINI_PLATES_QTY": order.mini_plates_qty ? String(order.mini_plates_qty) : ""
    };
    for (var frameName in frameMap) {
        if (setText(doc, frameName, frameMap[frameName]) === 0) missingFrames.push(frameName);
    }

    var missingCheckboxes = [];
    for (var i = 0; i < CHECKBOXES.length; i++) {
        var cbName = CHECKBOXES[i];
        var isChecked = !!(order.checkboxes && order.checkboxes[cbName]);
        if (setCheckbox(doc, cbName, isChecked) === 0) missingCheckboxes.push(cbName);
    }

    var proofItems = findByName(doc, "PROOF_THUMBNAIL");

    try { doc.save(); } catch (e) {}

    var summary = "Job Card filled for order #" + orderNum + "\n\n" +
        "Customer:   " + (order.customer_name || "") + "\n" +
        "Bike:       " + bike + "\n" +
        "Base:       " + (order.base_media || "") + "\n" +
        "Laminate:   " + (order.laminate || "") + "\n" +
        "Plastics:   " + (order.plastics_brand || "") + "\n" +
        "Designer:   " + initials + "\n\n" +
        "Checked add-ons:\n";
    var anyChecked = false;
    for (var j = 0; j < CHECKBOXES.length; j++) {
        if (order.checkboxes && order.checkboxes[CHECKBOXES[j]]) {
            summary += "  • " + CHECKBOXES[j].replace("CHK_", "").replace(/_/g, " ") + "\n";
            anyChecked = true;
        }
    }
    if (!anyChecked) summary += "  (none)\n";
    if (proofItems.length === 0) {
        summary += "\n⚠ PROOF_THUMBNAIL layer not found — place the artwork thumbnail before printing.";
    }
    if (missingFrames.length) summary += "\n⚠ Missing text frames: " + missingFrames.join(", ");
    if (missingCheckboxes.length) summary += "\n⚠ Missing checkbox groups: " + missingCheckboxes.join(", ");
    alert(summary);
})();
