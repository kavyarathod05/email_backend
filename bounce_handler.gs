/**
 * Google Apps Script for Bounce Email Processing and Blacklist Management.
 * This script should be added to your existing Google Apps Script bridge project.
 */

const BLACKLIST_SHEET_NAME = "Blacklist";

/**
 * Main function to search for bounce messages and extract failed emails.
 * Run this on a daily trigger.
 */
function processBounces() {
  const query = "from:mailer-daemon@googlemail.com";
  const threads = GmailApp.search(query);
  const blacklistSheet = getOrCreateSheet(BLACKLIST_SHEET_NAME);
  
  threads.forEach(thread => {
    const messages = thread.getMessages();
    messages.forEach(message => {
      const body = message.getPlainBody();
      
      // Improved Regex to extract the failed email address
      // Often found in "To: user@example.com" or "delivery to the following recipient failed: user@example.com"
      const emailRegex = /To:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/i;
      const match = body.match(emailRegex);
      
      if (match && match[1]) {
        const failedEmail = match[1].trim().toLowerCase();
        
        if (!isAlreadyBlacklisted(blacklistSheet, failedEmail)) {
          blacklistSheet.appendRow([failedEmail, new Date()]);
          Logger.log("Blacklisted: " + failedEmail);
        }
      }
      
      // Move processed bounce message to trash
      message.moveToTrash();
    });
  });
}

/**
 * Checks if an email is already in the blacklist sheet.
 */
function isAlreadyBlacklisted(sheet, email) {
  const data = sheet.getDataRange().getValues();
  for (let i = 0; i < data.length; i++) {
    if (data[i][0].toString().toLowerCase() === email.toLowerCase()) {
      return true;
    }
  }
  return false;
}

/**
 * Helper to get or create the Blacklist sheet.
 */
function getOrCreateSheet(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
    sheet.appendRow(["Email", "Timestamp"]);
    sheet.getRange(1, 1, 1, 2).setFontWeight("bold");
  }
  return sheet;
}

/**
 * Setting up a daily trigger programmatically.
 */
function setupDailyTrigger() {
  // Clear existing triggers for processBounces to avoid duplicates
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(t => {
    if (t.getHandlerFunction() === "processBounces") {
      ScriptApp.deleteTrigger(t);
    }
  });
  
  // Create daily trigger at 3 AM
  ScriptApp.newTrigger("processBounces")
    .timeBased()
    .everyDays(1)
    .atHour(3)
    .create();
  
  Logger.log("Daily trigger for processBounces has been set.");
}

/**
 * Update your existing doPost to handle blacklist checks.
 */
function doPost(e) {
  try {
    const params = JSON.parse(e.postData.contents);
    const action = params.action;
    
    if (action === "check_blacklist") {
      const email = params.email;
      const sheet = getOrCreateSheet(BLACKLIST_SHEET_NAME);
      const blacklisted = isAlreadyBlacklisted(sheet, email);
      return ContentService.createTextOutput(JSON.stringify({ 
        success: true, 
        blacklisted: blacklisted 
      })).setMimeType(ContentService.MimeType.JSON);
    }
    
    // Existing send email logic...
    if (params.to && params.subject && params.htmlBody) {
      GmailApp.sendEmail(params.to, params.subject, "", {
        htmlBody: params.htmlBody
      });
      return ContentService.createTextOutput("Success").setMimeType(ContentService.MimeType.TEXT);
    }

    return ContentService.createTextOutput("Error: Invalid parameters").setMimeType(ContentService.MimeType.TEXT);
  } catch (err) {
    return ContentService.createTextOutput("Error: " + err.toString()).setMimeType(ContentService.MimeType.TEXT);
  }
}
