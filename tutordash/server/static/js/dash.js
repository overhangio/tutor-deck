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
