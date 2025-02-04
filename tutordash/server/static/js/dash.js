if (window.location.href.indexOf("/plugin/store") > -1) {
    document.querySelectorAll('.sidebar-tab')[0].classList.toggle('sidebar-tab-selected');
    document.querySelectorAll('.tab-logo')[0].classList.toggle('sidebar-tab-logo-selected');
  } else {
    document.querySelectorAll('.sidebar-tab')[1].classList.toggle('sidebar-tab-selected');
    document.querySelectorAll('.tab-logo')[1].classList.toggle('sidebar-tab-logo-selected');
  }