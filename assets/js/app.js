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

var submissionStatusMap = new Map();

function uncollapseSubmissionIfFinished(_this, event) {
  for (var elem of event.target.children) {
    if (!("submissionId" in elem.dataset)) {
      continue;
    }

    var submissionId = elem.dataset.submissionId;
    var submissionStatus = elem.dataset.submissionStatus;

    if (!(submissionId in submissionStatusMap)) {
      submissionStatusMap[submissionId] = submissionStatus;
    }

    if (
      submissionStatus != submissionStatusMap[submissionId] &&
      ["E", "D"].includes(submissionStatus)
    ) {
      var submissionElem = document.getElementById(
        "submission-" + submissionId,
      );
      if (submissionElem.ariaExpanded == "false") {
        submissionElem.click();
      }
    }
    submissionStatusMap[submissionId] = submissionStatus;
  }
}
