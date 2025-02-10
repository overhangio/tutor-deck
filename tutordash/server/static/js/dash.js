if (window.location.href.indexOf("/plugin/store") > -1) {
    document.querySelectorAll('.sidebar-tab')[0].classList.toggle('sidebar-tab-selected');
    document.querySelectorAll('.sidebar-tab-logo')[0].classList.toggle('sidebar-tab-logo-selected');
  } else {
    document.querySelectorAll('.sidebar-tab')[1].classList.toggle('sidebar-tab-selected');
    document.querySelectorAll('.sidebar-tab-logo')[1].classList.toggle('sidebar-tab-logo-selected');
  }

document.getElementById("search-input").addEventListener("input", function() {
  let filter = this.value.toLowerCase(); 
  let plugins = document.querySelectorAll(".installed-plugin"); 

  plugins.forEach(plugin => {
      let name = plugin.querySelector(".name a").textContent.toLowerCase();
      if (name.includes(filter)) {
          plugin.style.display = ""; 
      } else {
          plugin.style.display = "none"; 
      }
  });
});