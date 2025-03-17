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

function setToastContent(cmd) {
	let toast_title = document.getElementById("toast-title");
	let toast_description = document.getElementById("toast-description");
	let toast_footer = document.getElementById("toast-footer");

	if (cmd.startsWith("$ tutor plugins enable")) {
		toast_title.textContent = "Your plugin was successfully enabled";
		toast_description.textContent =
			"Running local launch will allow all changes to plugins to take effect. This could take a few minutes to complete.";
	} else if (cmd.startsWith("$ tutor plugins upgrade")) {
		toast_title.textContent = "Your plugin was successfully updated";
		toast_description.textContent =
			"Running local launch will allow all changes to plugins to take effect. This could take a few minutes to complete.";
	} else if (cmd.startsWith("$ tutor plugins install")) {
		toast_title.textContent = "Plugin Installed Successfully";
		toast_description.textContent =
			"Enable it now to start using its features";
		toast_footer.style.display = "none";
	} else if (cmd.startsWith("$ tutor config save")) {
		toast_title.textContent = "You have successfully modified parameters";
		toast_description.textContent =
			"Running local launch will allow all changes to plugins to take effect. This could take a few minutes to complete.";
	} else if (cmd.startsWith("$ tutor local launch")) {
		toast_title.textContent = "Local launch was successfully executed";
		toast_footer.style.display = "none";
	}
}

let executed_new_command = true;
let log_count = 0;
htmx.on("htmx:sseBeforeMessage", function (evt) {
	log_count += 1;

	// Don't swap content, we want to append
	evt.preventDefault();

	const stdout = JSON.parse(evt.detail.data);
	const text = document.createTextNode(stdout);

	if (log_count === 1) {
		// First log element contains the name of logging file
		let lastLogFile = getCookie("last-log-file");
		// If the new log file name is same as the previous log file name that means
		// we have not executed a new command, they are logs of the last executed command
		if (lastLogFile === text.nodeValue.trim()) {
			executed_new_command = false;
		} else {
			// We are indeed executing a new command so show cancel button and update log file name
			ShowCancelCommandButton();
			setCookie("last-log-file", text.nodeValue.trim(), 1);
		}
	} else if (log_count === 2) {
		// Second log element is the running command, make toast here
		cmd = text.nodeValue.trim();
		setToastContent(cmd);
	} else {
		// Only show toast if it was a new command
		if (executed_new_command === true) {
			// If command has run successfully show the toast message
			if (stdout.includes("Success!")) {
				showToast("info");
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
