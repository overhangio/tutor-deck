const logsElement = document.getElementById('tutor-logs');

// Track whether we should autoscroll
let shouldAutoScroll = true;

// When user manually scrolls, update behaviour
logsElement.addEventListener('scroll', function() {
  // Only update shouldAutoScroll if this is a user-initiated scroll
  if (!isScrollingProgrammatically) {
  shouldAutoScroll = false;
  }
});

// Track programmatic scrolling to avoid feedback loops
let isScrollingProgrammatically = false;

htmx.on("htmx:sseBeforeMessage", function(evt) {
  // Don't swap content, we want to append
  evt.preventDefault();
  
  // Parse JSON
  const stdout = JSON.parse(evt.detail.data);
  // If command has run successfully show the toast message, show the enable/disable bar, update page button
  if (stdout.includes("Success!")){
    showToast("info");
    if (window.pluginName){
      window.pluginIsInstalled = true;
      togglePluginEnableDisableBar(true);
      showPluginPageButton();
    }
  }

  if (stdout.includes("Cancelled!")){
    showPluginPageButton();
  }

  
  // Note that HTML is automatically escaped
  const text = document.createTextNode(stdout);
  evt.detail.elt.appendChild(text);
  
  // Scroll to bottom only if shouldAutoScroll is true
  if (shouldAutoScroll) {
  isScrollingProgrammatically = true;
  evt.detail.elt.scrollTop = evt.detail.elt.scrollHeight;
  
  // Reset the flag after a short delay
  setTimeout(() => {
      isScrollingProgrammatically = false;
  }, 10);
  }
});

// Additional handlers for scroll inputs
logsElement.addEventListener('wheel', function() {
  shouldAutoScroll = false;
}, { passive: true });

logsElement.addEventListener('touchstart', function() {
  shouldAutoScroll = false;
}, { passive: true });