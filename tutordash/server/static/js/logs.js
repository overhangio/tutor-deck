let shouldAutoScroll = true;
let isScrollingProgrammatically = false;
// When user manually scrolls, update behaviour
logsElement.addEventListener("scroll", function () {
	if (!isScrollingProgrammatically) {
		shouldAutoScroll = false;
	}
});

let isFirstLog = true;
let executed_new_command = true;
htmx.on("htmx:sseBeforeMessage", function (evt) {
	// Don't swap content, we want to append
	evt.preventDefault();

	const stdout = JSON.parse(evt.detail.data);
	const text = document.createTextNode(stdout);

	// First log element contains the name of loggin file
	if (isFirstLog === true) {
		isFirstLog = false;
		let lastLogFile = getCookie("last-log-file");
		// If the new log file name is same as the previous log file name that means
		// we have not executed a new command, they are logs of the last executed command
		if (lastLogFile === text.nodeValue.trim()) {
			executed_new_command = false;
		} else {
			// We are indeed executing a new command so show cancel button and update log file name
			showCancelButton();
			setCookie("last-log-file", text.nodeValue.trim(), 1);
		}
	} else {
		if (!window.location.pathname.includes("advanced")) {
			// Only show toast if it was a new command
			if (executed_new_command === true) {
				if (stdout.includes("Success!")) {
					showToast("info");
					if (pluginName) {
						// If command has run successfully show the toast message
						// Successfull command means plugin is either successfully installed or upgraded
						// In either case we can safely display the enable/disable bar
						// And show the plugin upgrade page button
						isPluginInstalled = true;
						showPluginEnableDisableBar();
						showPluginPageButton();
					} else {
						ShowLocalLaunchButton();
					}
				}
				if (stdout.includes("Cancelled!")) {
					if (pluginName) {
						showPluginPageButton(isPluginInstalled);
					} else {
						ShowLocalLaunchButton();
					}
				}
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

// last_command_executed = logsElement.textContent.split("\n")[0].split("$")[1].trim();
