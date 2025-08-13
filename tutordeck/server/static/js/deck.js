// Cookie utilities
// We can't use the cookieStore because we might want to access tutor deck in http mode,
// where it is not available.
function getCookie(name) {
	let nameEQ = name + "=";
	return (
		document.cookie
			.split(";")
			.map((cookie) => cookie.trim())
			.find((cookie) => cookie.startsWith(nameEQ))
			?.slice(nameEQ.length) || null
	);
}
function eraseCookie(name) {
	document.cookie =
		name + "=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;";
}

// Handle plugins requiring launch based on the values in the corresponding cookie
const pluginsRequireLaunchCookieName = "plugins-require-launch";
function displayPluginsRequireLaunchWarning() {
	const cookie = getCookie(pluginsRequireLaunchCookieName);
	if (cookie) {
		const cookieValue = cookie.slice(1, -1); // remove quotes
		cookieValue.split('+').map(s => s.trim()).forEach(plugin => {
			document.querySelectorAll(`[data-plugin="${plugin}"] .warning-launch-required`).forEach(element => {
				element.classList.add("visible");
				document.getElementById('warning-launch-required-main').classList.add("visible");
			});
		});
	}
}
document.body.addEventListener('htmx:afterOnLoad', function(event) {
	displayPluginsRequireLaunchWarning();
});

// Handle modal
const modalContainer = document.getElementById("modal_container");
const openModalButton = document.querySelector(".open-modal-button");
const closeModalButton = document.querySelector(".close-modal-button");

openModalButton?.addEventListener("click", () => {
	modalContainer.classList.add("show");
});
closeModalButton?.addEventListener("click", () => {
	modalContainer.classList.remove("show");
});

// Handle toast
const toast = document.querySelector(".toast");
let closeToastButtons = document.querySelectorAll(".close-toast-button");

closeToastButtons.forEach((button) => {
	button.addEventListener("click", () => {
		hideToast(toast);
	});
});
function showLaunchSuccessfulToast() {
	// TODO this is very brittle because it relies on static variables and string values.
	if (toast) {
		if (toastTitle === "Launch platform was successfully executed") {
			eraseCookie(pluginsRequireLaunchCookieName);
		}
		toast.style.display = "flex";
		setTimeout(() => {
			void toast.offsetHeight;
			toast.classList.add("active");
		}, 1);
	}
}
function hideToast() {
	if (toast) {
		toast.classList.remove("active");
		setTimeout(() => {
			toast.style.display = "none";
		}, 500);
	}
}

const launchDescription = "To apply the changes, run Launch Platform. This will update your platform and may take a few minutes to complete.";
const TOAST_CONFIGS = {
	"tutor config save": {
		title: "Configuration parameters were updated",
		description: launchDescription,
		showFooter: true,
	},
	"tutor local launch": {
		title: "Platform was launched",
		description: "",
		showFooter: false,
	},
	"tutor plugins install": {
		title: "Plugin was installed",
		description: "Enable it now to start using its features",
		showFooter: false,
	},
	"tutor plugins enable": {
		title: "Plugin was enabled",
		description: launchDescription,
		showFooter: true,
	},
	"tutor plugins upgrade": {
		title: "Plugin was updated",
		description: launchDescription,
		showFooter: true,
	},
};
let toastTitle = document.getElementById("toast-title");
let toastDescription = document.getElementById("toast-description");
let toastFooter = document.getElementById("toast-footer");
function setToastContent(cmd) {
	const matchedPrefix = Object.keys(TOAST_CONFIGS).find((prefix) =>
		cmd.startsWith(prefix)
	);
	if (matchedPrefix) {
		const config = TOAST_CONFIGS[matchedPrefix];
		toastTitle.textContent = config.title;
		toastDescription.textContent = config.description;
		toastFooter.style.display = config.showFooter ? "flex" : "none";
	}
}

// Each page defines its own relevant commands, we use them to check
// if the currently running commands belong the currently opened page or not.
// A "*" relevant command matches all possible commands.
let tutorCommandsToWatch = [];

