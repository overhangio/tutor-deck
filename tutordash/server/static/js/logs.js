const logsElement = document.getElementById("tutor-logs");

let shouldAutoScroll = true;
// When user manually scrolls, update behaviour
logsElement.addEventListener("scroll", function () {
	if (!isScrollingProgrammatically) {
		shouldAutoScroll = false;
	}
});
let isScrollingProgrammatically = false;

htmx.on("htmx:sseBeforeMessage", function (evt) {
	// Don't swap content, we want to append
	evt.preventDefault();

	const stdout = JSON.parse(evt.detail.data);
	if (!window.location.pathname.includes("advanced")) {
		if (stdout.includes("Success!")) {
			// If command has run successfully show the toast message, show the enable/disable bar, update page button
			showToast("info");
			if (window.pluginName) {
				window.pluginIsInstalled = true;
				togglePluginEnableDisableBar(true);
				showPluginPageButton();
			} else {
				ShowLocalLaunchButton();
			}
		}
		if (stdout.includes("Cancelled!")) {
			if (window.pluginName) {
				showPluginPageButton();
			} else {
				ShowLocalLaunchButton();
			}
		}
	}

	const text = document.createTextNode(stdout);
	evt.detail.elt.appendChild(text);

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
