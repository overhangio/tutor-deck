// Most of the websites dynamic functionality depends on the content of the logs
// This file is responsible for:
// 1) calling functions to set and display toast messages
// 2) calling functions to toggle command execution/cancellation buttons
// 3) logs scrolling

// Each page that uses logs defines its own command execution/cancellation toggle functions with the same signature
// We can safely call these functions and their functionality will be handeled by the page specific js

let shouldAutoScroll = true;
let isScrollingProgrammatically = false;
// When user manually scrolls, update behaviour
logsElement.addEventListener("scroll", function () {
	if (!isScrollingProgrammatically) {
		shouldAutoScroll = false;
	}
});
let executedNewCommand = false;
htmx.on("htmx:sseBeforeMessage", function (evt) {
	// Don't swap content, we want to append
	evt.preventDefault();

	const data = JSON.parse(evt.detail.data);
	const command = data.command;

	// This means a parallel command is executing
	if (data.thread_alive) {
		// Check if we are on the same page on which the actual command was executed
		// Each page defines its relevant commands which are sent to `onRelevantPage` function to check if we are on the relevant page
		if (onRelevantPage(command)) {
			ShowCancelCommandButton();
			logsElement.style.display = "block";
		} else {
			// If we are not on relevant page we don't show the cancel button and disable all inputs
			deactivateInputs();
		}
		executedNewCommand = true;
	}

	const parallelCommandCompleted = executedNewCommand && !data.thread_alive;

	const onPluginPage = typeof pluginName !== "undefined";
	// Note that sequential commands are only executed on the plugins page
	// Refreshing the page will run this block again
	// Because there is no way to determine if its a newly executed sequential command or an old one
	if (
		parallelCommandCompleted ||
		(onPluginPage && sequentialCommandExecuted)
	) {
		activateInputs();
		// There are certain commands for which we do not show the toast message
		// Only show the toast if it was set in the `setToastContent` function and if the command ran successfully
		if (data.stdout.includes("Success!")) {
			setToastContent(command);
			if (toastTitle.textContent.trim()) {
				showToast("info");
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
	evt.detail.elt.appendChild(document.createTextNode(data.stdout));
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
