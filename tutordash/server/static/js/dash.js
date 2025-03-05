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


let close_toast = document.querySelector(".close-toast-button");
let toast = document.querySelector(".toast");

if (close_toast !== null){
  close_toast.addEventListener("click", () => {
    hideToast();
  });
}


function showToast(type = "success") {
  const toast = document.querySelector(".toast");
  if (toast !== null) {
    toast.style.display = "flex"; // Show the toast
    setTimeout(() => {
      void toast.offsetHeight;
      toast.classList.add("active");
    }, 1);

    // Auto-remove toast after 5s
    setTimeout(() => {
      hideToast();
    }, 5000);
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
