(function () {
  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function formatDate(date) {
    return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());
  }

  function updateSummary() {
    var dateEl = document.querySelector("[data-summary-date]");
    var timeEl = document.querySelector("[data-summary-time]");
    if (!dateEl && !timeEl) return;
    var dateInput = document.querySelector("input[name='preferred_date']");
    var dateValue = dateInput ? dateInput.value : "";
    var timeInput = document.querySelector("input[name='arrival_window']:checked");
    var timeValue = timeInput ? timeInput.value : "";
    if (dateEl) {
      var fallbackDate = dateEl.getAttribute("data-default") || "";
      dateEl.textContent = dateValue || fallbackDate;
    }
    if (timeEl) {
      var fallbackTime = timeEl.getAttribute("data-default") || "";
      timeEl.textContent = (timeValue ? " | " + timeValue : " | " + fallbackTime).trim();
    }
  }

  function buildCalendar(container) {
    var selectedValue = container.getAttribute("data-selected") || "";
    var selectedDate = selectedValue ? new Date(selectedValue) : new Date();
    if (isNaN(selectedDate.getTime())) {
      selectedDate = new Date();
    }
    var month = selectedDate.getMonth();
    var year = selectedDate.getFullYear();
    var hiddenInput = container.parentElement.querySelector('input[name="preferred_date"]');

    function render() {
      container.innerHTML = "";
      var header = document.createElement("div");
      header.className = "eb-calendar-header";

      var title = document.createElement("div");
      var monthName = new Date(year, month, 1).toLocaleString("default", { month: "long" });
      title.textContent = monthName + " " + year;

      var nav = document.createElement("div");
      nav.className = "eb-calendar-nav";

      var prevBtn = document.createElement("button");
      prevBtn.type = "button";
      prevBtn.className = "eb-calendar-btn";
      prevBtn.textContent = "<";
      prevBtn.addEventListener("click", function () {
        month -= 1;
        if (month < 0) {
          month = 11;
          year -= 1;
        }
        render();
      });

      var nextBtn = document.createElement("button");
      nextBtn.type = "button";
      nextBtn.className = "eb-calendar-btn";
      nextBtn.textContent = ">";
      nextBtn.addEventListener("click", function () {
        month += 1;
        if (month > 11) {
          month = 0;
          year += 1;
        }
        render();
      });

      nav.appendChild(prevBtn);
      nav.appendChild(nextBtn);
      header.appendChild(title);
      header.appendChild(nav);

      var grid = document.createElement("div");
      grid.className = "eb-calendar-grid";
      var weekDays = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"];
      weekDays.forEach(function (day) {
        var cell = document.createElement("div");
        cell.textContent = day;
        cell.className = "eb-calendar-day is-muted";
        grid.appendChild(cell);
      });

      var firstDay = new Date(year, month, 1);
      var startOffset = (firstDay.getDay() + 6) % 7;
      var daysInMonth = new Date(year, month + 1, 0).getDate();

      for (var i = 0; i < startOffset; i += 1) {
        var emptyCell = document.createElement("div");
        emptyCell.className = "eb-calendar-day is-muted";
        emptyCell.textContent = "";
        grid.appendChild(emptyCell);
      }

      for (var dayNum = 1; dayNum <= daysInMonth; dayNum += 1) {
        (function (dayNumber) {
          var cell = document.createElement("button");
          cell.type = "button";
          cell.className = "eb-calendar-day";
          cell.textContent = dayNumber;
          var cellDate = new Date(year, month, dayNumber);
          var cellValue = formatDate(cellDate);
          if (selectedValue === cellValue) {
            cell.classList.add("is-selected");
          }
          cell.addEventListener("click", function () {
            selectedValue = cellValue;
            if (hiddenInput) {
              hiddenInput.value = cellValue;
            }
            updateSummary();
            render();
          });
          grid.appendChild(cell);
        })(dayNum);
      }

      container.appendChild(header);
      container.appendChild(grid);
    }

    if (hiddenInput && hiddenInput.value) {
      selectedValue = hiddenInput.value;
    }

    render();
  }

  document.querySelectorAll(".eb-calendar").forEach(function (container) {
    buildCalendar(container);
  });

  document.querySelectorAll("input[name='arrival_window']").forEach(function (input) {
    input.addEventListener("change", updateSummary);
  });
  updateSummary();

  function toggleContactBlocks() {
    var privateBlock = document.querySelector("[data-private]");
    var businessBlock = document.querySelector("[data-business]");
    if (!privateBlock && !businessBlock) return;
    var inputs = document.querySelectorAll("input[name='customer_type']");
    if (!inputs.length) return;
    var type = "private";
    inputs.forEach(function (input) {
      if (input.checked) type = input.value;
    });
    if (privateBlock) privateBlock.classList.toggle("is-visible", type === "private");
    if (businessBlock) businessBlock.classList.toggle("is-visible", type === "business");
  }

  document.querySelectorAll("input[name='customer_type']").forEach(function (input) {
    input.addEventListener("change", toggleContactBlocks);
  });
  toggleContactBlocks();
})();

