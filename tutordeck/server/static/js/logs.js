// Most of the websites dynamic functionality depends on the content of the logs
// This file is responsible for:
// 1) calling functions to set and display toast messages
// 2) calling functions to toggle command execution/cancellation buttons
// 3) logs scrolling

// Each page that uses logs defines its own command execution/cancellation toggle functions with the same signature
// We can safely call these functions and their functionality will be handeled by the page specific js

// Scrolling management
let shouldAutoScroll = true;
let isScrollingProgrammatically = false;
// When user manually scrolls, update behaviour
logsElement.addEventListener(
	"scroll",
	function () {
		if (!isScrollingProgrammatically) {
			shouldAutoScroll = false;
		}
	}
);
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

let commandExecuted = false;
function checkAndClearCommandExecuted() {
	const commandExecutedCookieName = "command-executed";
	if (getCookie(commandExecutedCookieName)) {
		eraseCookie(commandExecutedCookieName);
		commandExecuted = true;
	}
};
checkAndClearCommandExecuted();

let threadWasAlive = false;
htmx.on("htmx:sseBeforeMessage", function (evt) {
	// Don't swap content, we want to append
	evt.preventDefault();
	const data = JSON.parse(evt.detail.data);
	evt.detail.elt.appendChild(document.createTextNode(data.stdout));

	// This means a parallel command is executing
	if (data.thread_alive) {
		threadWasAlive = true;
		// Check if we are on the same page on which the actual command was executed
		// Each page defines its relevant commands that are monitored and that will trigger a display of the log window.
		let shouldDisplayLogs = tutorCommandsToWatch.some(
			(prefix) => prefix === "*" || data.command.startsWith(prefix)
		);
		if(shouldDisplayLogs) {
			ShowCancelCommandButton();
			logsElement.style.display = "block";
		} else {
			// If we are not on relevant page we don't show the cancel button and disable all inputs
			onCommandRunning();
		}
	}

	// A parallel command was running, and now it's completed
	const parallelCommandCompleted = threadWasAlive && !data.thread_alive;
	// TODO this is a very brittle way of checking that we are on a plugin page... Let's not use static variables.
	const onPluginPage = typeof pluginName !== "undefined";
	// Note that sequential commands are only executed on the plugins page
	// Refreshing the page will run this block again
	// Because there is no way to determine if its a newly executed sequential command or an old one
	if (parallelCommandCompleted || commandExecuted) {
		onCommandComplete();
		// There are certain commands for which we do not show the toast message
		// Only show the toast if it was set in the `setToastContent` function and if the command ran successfully
		// TODO this is brittle because it relies on a hard-coded "Success!" string that is sent from the backend.
		if (data.stdout.includes("Success!")) {
			setToastContent(data.command);
			if (toastTitle.textContent.trim()) {
				showLaunchSuccessfulToast();
			}
		}
		if (onPluginPage) {
			checkIfPluginInstalled(pluginName).then((isInstalled) => {
				if (isInstalled) {
					isPluginInstalled = true;
				}
				showPluginEnableDisableBar();
				ShowRunCommandButton();
			});
		} else {
			ShowRunCommandButton();
		}
	}

	// Scrolling management
	if (shouldAutoScroll) {
		// Set flag so event listener knows we are scrolling programmatically
		isScrollingProgrammatically = true;
		evt.detail.elt.scrollTop = evt.detail.elt.scrollHeight;

		// Reset the flag after a short delay
		setTimeout(() => {
			isScrollingProgrammatically = false;
		}, 10);
	}
});

// TODO we removed all code in these functions, which was too extensive. We should now clean this up.
function onCommandComplete() {
	// // This is to enable "cancel" buttons. But as a side effect, it's causing all disable inputs to be
	// // enabled, which is an error in some cases (e.g: "unset buttons")
	// document.querySelectorAll("button").forEach((button) => {
	// 	button.disabled = false;
	// });
	// document.querySelectorAll("input").forEach((input) => {
	// 	input.disabled = false;
	// });
	// document.querySelectorAll(".form-switch").forEach((formSwitch) => {
	// 	formSwitch.style.opacity = 1;
	// });
	document.body.classList.remove("command-running");
}
function onCommandRunning() {
	// // This is to prevent running additional commands at the same time as a long-running
	// // command. But it's way too extensive. We shouldn't disable ALL inputs.
	// document.querySelectorAll("button").forEach((button) => {
	// 	button.disabled = true;
	// });
	// document.querySelectorAll("input").forEach((input) => {
	// 	input.disabled = true;
	// });
	// document.querySelectorAll(".form-switch").forEach((formSwitch) => {
	// 	formSwitch.style.opacity = 0.5;
	// });
	document.body.classList.add("command-running");
}
