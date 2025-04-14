function setCookie(name, value, days) {
	let expires = "";
	if (days) {
		let date = new Date();
		date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
		expires = "; expires=" + date.toUTCString();
	}
	document.cookie = `${name}=${value || ""}${expires}; path=/`;
}
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
function showToast() {
	if (toast) {
		if (toastTitle === "Launch platform was successfully executed") {
			document.cookie.split(";").forEach((cookie) => {
				let name = cookie.split("=")[0].trim();
				if (name.startsWith("warning-cookie")) {
					eraseCookie(name);
				}
			});
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
	"$ tutor plugins enable": {
		title: "Your plugin was successfully enabled",
		description:
			"To apply the changes, run Launch Platform. This will update your platform and may take a few minutes to complete.",
		showFooter: true,
	},
	"$ tutor plugins upgrade": {
		title: "Your plugin was successfully updated",
		description:
			"To apply the changes, run Launch Platform. This will update your platform and may take a few minutes to complete.",
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
			"To apply the changes, run Launch Platform. This will update your platform and may take a few minutes to complete.",
		showFooter: true,
	},
	"$ tutor local launch": {
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
