// Handle plugins requiring launch based on the values in the corresponding cookie
const pluginsRequireLaunchCookieName = "plugins-require-launch";
async function displayPluginsRequireLaunchWarning() {
	const cookie = await cookieStore.get(pluginsRequireLaunchCookieName);
	if (cookie && cookie.value) {
		const cookieValue = cookie.value.slice(1, -1); // remove quotes
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
			cookieStore.delete(pluginsRequireLaunchCookieName);
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

const TOAST_CONFIGS = {
	"tutor plugins enable": {
		title: "Your plugin was successfully enabled",
		description:
			"To apply the changes, run Launch Platform. This will update your platform and may take a few minutes to complete.",
		showFooter: true,
	},
	"tutor plugins upgrade": {
		title: "Your plugin was successfully updated",
		description:
			"To apply the changes, run Launch Platform. This will update your platform and may take a few minutes to complete.",
		showFooter: true,
	},
	"tutor plugins install": {
		title: "Plugin Installed Successfully",
		description: "Enable it now to start using its features",
		showFooter: false,
	},
	"tutor config save": {
		title: "You have successfully modified parameters",
		description:
			"To apply the changes, run Launch Platform. This will update your platform and may take a few minutes to complete.",
		showFooter: true,
	},
	"tutor local launch": {
		title: "Launch platform was successfully executed",
		description: "",
		showFooter: false,
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
// if the currently running commands belong the currently opened page or not
let relevantCommands = [];
let onDeveloperPage = false;
function onRelevantPage(command) {
	if (onDeveloperPage) {
		// Developer page is relevant to all commands
		return true;
	}
	return relevantCommands.some((prefix) => command.startsWith(prefix));
}

function activateInputs() {
	document.querySelectorAll("button").forEach((button) => {
		button.disabled = false;
	});
	document.querySelectorAll("input").forEach((input) => {
		input.disabled = false;
	});
	document.querySelectorAll(".form-switch").forEach((formSwitch) => {
		formSwitch.style.opacity = 1;
	});
	document.getElementById("warning-command-running").style.display = "none";
}
function deactivateInputs() {
	document.querySelectorAll("button").forEach((button) => {
		button.disabled = true;
	});
	document.querySelectorAll("input").forEach((input) => {
		input.disabled = true;
	});
	document.querySelectorAll(".form-switch").forEach((formSwitch) => {
		formSwitch.style.opacity = 0.5;
	});
	document.getElementById("warning-command-running").style.display = "flex";
}
