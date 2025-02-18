function SetWarning(){
  const warningElements = document.querySelectorAll('[id$="-warning"]');
  const warningMain = document.getElementById('warning-main');
  warningElements.forEach(function(warningElement) {
    const pluginName = warningElement.id.replace('-warning', '');
    if (document.cookie.includes(pluginName)) {
        warningElement.style.display = 'block';  
        warningMain.style.display = 'flex';
    }
  });
}
SetWarning()


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
