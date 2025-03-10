function SetWarning(){
  const warningElements = document.querySelectorAll('[id^="warning-cookie-"]');
  const warningMain = document.getElementById('warning-main');
  warningElements.forEach(function(warningElement) {
    if (document.cookie.includes(warningElement.id)) {
        warningElement.style.display = 'flex';  
        warningMain.style.display = 'flex';
    }
  });
}
document.body.addEventListener('htmx:afterOnLoad', function(event) {
  SetWarning();
});


let open = document.querySelectorAll(".open-modal-button");
const modal_container = document.getElementById("modal_container");
let close = document.querySelectorAll(".close-modal-button");

open.forEach((button) => {
	button.addEventListener("click", () => {
		modal_container.classList.add("show");
	});
});

close.forEach((button) => {
	button.addEventListener("click", () => {
		modal_container.classList.remove("show");
	});
});


let closeToastButtons = document.querySelectorAll(".close-toast-button");
const toast = document.querySelector(".toast");

closeToastButtons.forEach((button) => {
  button.addEventListener("click", () => {
      hideToast(toast);
  });
});

function showToast(type = "success") {
  if (toast !== null) {
    toast.style.display = "flex"; // Show the toast
    setTimeout(() => {
      void toast.offsetHeight;
      toast.classList.add("active");
    }, 1);
  }
}

function hideToast() {
  if (toast !== null) {
    toast.classList.remove("active");

    // Wait for transition to complete before removing container
    setTimeout(() => {
      toast.style.display = "none";
    }, 500); // Match this to the CSS transition duration
  }
}
