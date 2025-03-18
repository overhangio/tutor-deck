function setCookie(name, value, days) {
	var expires = "";
	if (days) {
		var date = new Date();
		date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
		expires = "; expires=" + date.toUTCString();
	}
	document.cookie = name + "=" + (value || "") + expires + "; path=/";
}
function getCookie(name) {
	var nameEQ = name + "=";
	var ca = document.cookie.split(";");
	for (var i = 0; i < ca.length; i++) {
		var c = ca[i];
		while (c.charAt(0) == " ") c = c.substring(1, c.length);
		if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
	}
	return null;
}
function eraseCookie(name) {
	document.cookie =
		name + "=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;";
}

// Handle modal
const modal_container = document.getElementById("modal_container");
let open_modal_button = document.querySelector(".open-modal-button");
let close_modal_button = document.querySelector(".close-modal-button");
if (open_modal_button !== null) {
	open_modal_button.addEventListener("click", () => {
		modal_container.classList.add("show");
	});
}
if (close_modal_button !== null) {
	close_modal_button.addEventListener("click", () => {
		modal_container.classList.remove("show");
	});
}

// Handle toast
const toast = document.querySelector(".toast");
let closeToastButtons = document.querySelectorAll(".close-toast-button");

closeToastButtons.forEach((button) => {
	button.addEventListener("click", () => {
		hideToast(toast);
	});
});
function showToast() {
	if (toast !== null) {
		toast.style.display = "flex";
		setTimeout(() => {
			void toast.offsetHeight;
			toast.classList.add("active");
		}, 1);
	}
}
function hideToast() {
	if (toast !== null) {
		toast.classList.remove("active");
		setTimeout(() => {
			toast.style.display = "none";
		}, 500);
	}
}

const TOAST_CONFIGS = {
	"$ tutor plugins enable": {
		title: "Your plugin was successfully enabled",
		description:
			"Running local launch will allow all changes to plugins to take effect. This could take a few minutes to complete.",
		showFooter: true,
	},
	"$ tutor plugins upgrade": {
		title: "Your plugin was successfully updated",
		description:
			"Running local launch will allow all changes to plugins to take effect. This could take a few minutes to complete.",
		showFooter: true,
	},
	"$ tutor plugins install": {
		title: "Plugin Installed Successfully",
		description: "Enable it now to start using its features",
		showFooter: false,
	},
	"$ tutor config save": {
		title: "You have successfully modified parameters",
		description:
			"Running local launch will allow all changes to plugins to take effect. This could take a few minutes to complete.",
		showFooter: true,
	},
	"$ tutor local launch": {
		title: "Local launch was successfully executed",
		description: "",
		showFooter: false,
	},
};

let toast_title = document.getElementById("toast-title");
let toast_description = document.getElementById("toast-description");
let toast_footer = document.getElementById("toast-footer");
function setToastContent(cmd) {
	const matchedPrefix = Object.keys(TOAST_CONFIGS).find((prefix) =>
		cmd.startsWith(prefix)
	);
	if (matchedPrefix) {
		const config = TOAST_CONFIGS[matchedPrefix];
		toast_title.textContent = config.title;
		toast_description.textContent = config.description;
		toast_footer.style.display = config.showFooter ? "flex" : "none";
	}
}
