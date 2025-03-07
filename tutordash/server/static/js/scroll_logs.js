// Track whether we should autoscroll
let shouldAutoScroll = true;
const logsElement = document.getElementById('tutor-logs');

// Function to check if we are at the bottom
function isAtBottom() {
  const scrollPosition = logsElement.scrollTop + logsElement.clientHeight;
  // Allow small margin of error (1px)
  return Math.abs(scrollPosition - logsElement.scrollHeight) <= 1;
}

// When user manually scrolls, update behaviour
logsElement.addEventListener('scroll', function() {
  // Only update shouldAutoScroll if this is a user-initiated scroll
  if (!isScrollingProgrammatically) {
  shouldAutoScroll = isAtBottom();
  }
});

// Track programmatic scrolling to avoid feedback loops
let isScrollingProgrammatically = false;

htmx.on("htmx:sseBeforeMessage", function(evt) {
  // Don't swap content, we want to append
  evt.preventDefault();
  
  // Parse JSON
  const stdout = JSON.parse(evt.detail.data);
  if (stdout.includes("Success!")){
    showToast("info");
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