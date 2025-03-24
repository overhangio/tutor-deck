// Most of the websites dynamic functionality depends on the content of the logs
// This file is responsible for:
// 1) setting and displaying toast messages
// 2) toggling command execution/cancellation buttons
// 3) logs scrolling

// Each page that uses logs defines its own command execution/cancellation toggle functions with the same names
// We can safely call these functions and their functionality will be handeled by the page specific js

let shouldAutoScroll = true;
let isScrollingProgrammatically = false;
// When user manually scrolls, update behaviour
logsElement.addEventListener("scroll", function () {
  if (!isScrollingProgrammatically) {
    shouldAutoScroll = false;
  }
});

let executedNewCommand = true;
let logsCount = 0;
let currentLogFile = null;
htmx.on("htmx:sseBeforeMessage", function (evt) {
  logsCount += 1;
  // Don't swap content, we want to append
  evt.preventDefault();

  const stdout = JSON.parse(evt.detail.data);
  const text = document.createTextNode(stdout);
  // First log element contains the name of logging file
  if (logsCount === 1) {
    currentLogFile = text.nodeValue.trim();

    let lastLogFile = getCookie("last-log-file");

    // If the new log file name is same as the previous log file name that means
    // we have not executed a new command, they are logs of the last executed command
    if (lastLogFile === currentLogFile) {
      executedNewCommand = false;
    } else {
      // We are indeed executing a new command so show cancel button and update log file name
      ShowCancelCommandButton();
    }
  } else if (logsCount === 2) {
    // Second log element is the running command, make toast here
    cmd = text.nodeValue.trim();
    setToastContent(cmd);
    evt.detail.elt.appendChild(text);
  } else {
    // Only show toast if it was a new command
    if (executedNewCommand === true) {
      // If command has run successfully update UI
      if (stdout.includes("Success!")) {
        setCookie("last-log-file", currentLogFile, 365);
        // Do not show the toast if it is empty
        if (toastTitle.textContent.trim() != "") {
          showToast("info");
        }
        // Check if we are on the plugin page
        if (typeof pluginName !== "undefined") {
          // Successfull command means plugin is either successfully installed or upgraded
          // In either case we can safely display the enable/disable bar
          isPluginInstalled = true;
          showPluginEnableDisableBar();
        }
        ShowRunCommandButton();
      }
      if (stdout.includes("Cancelled!")) {
        ShowRunCommandButton();
      }
    }
    evt.detail.elt.appendChild(text);
  }
  if (shouldAutoScroll) {
    // Set flag so event listner knows we are scrolling programatically
    isScrollingProgrammatically = true;
    evt.detail.elt.scrollTop = evt.detail.elt.scrollHeight;

    // Reset the flag after a short delay
    setTimeout(() => {
      isScrollingProgrammatically = false;
    }, 10);
  }
});

// Additional handlers for scroll inputs
logsElement.addEventListener(
  "wheel",
  function () {
    shouldAutoScroll = false;
  },
  { passive: true }
);

logsElement.addEventListener(
  "touchstart",
  function () {
    shouldAutoScroll = false;
  },
  { passive: true }
);
