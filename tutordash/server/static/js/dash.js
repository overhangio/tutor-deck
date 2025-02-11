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