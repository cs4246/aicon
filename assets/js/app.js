$("#per_page").change(function (e) {
  window.location.href = $(this).val();
});

$(document).ready(function () {
  $(document).on("click", ".clickable input", function (event) {
    event.stopPropagation();
  });

  $(document).on("click", ".clickable a", function (event) {
    event.stopPropagation();
  });
});
