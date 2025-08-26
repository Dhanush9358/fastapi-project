// static/script.js
document.addEventListener("DOMContentLoaded", () => {
  /* ----------------------------
     Generic helpers
     ---------------------------- */
  const hhmm = v => (v || "").slice(0, 5);

  /* ----------------------------
     Book page: enforce min start time when date == today
     Targets: templates/book.html
     ---------------------------- */
  (function attachBookPageLogic() {
    const dateInput = document.getElementById("date");
    const startInput = document.getElementById("start_time");
    if (!dateInput || !startInput) return;

    const setMinStartTime = () => {
      const today = new Date().toISOString().split("T")[0];
      const selectedDate = dateInput.value;
      if (selectedDate === today) {
        const now = new Date();
        const hours = String(now.getHours()).padStart(2, "0");
        const minutes = String(now.getMinutes()).padStart(2, "0");
        startInput.min = `${hours}:${minutes}`;
      } else {
        startInput.removeAttribute("min");
      }
    };

    dateInput.addEventListener("change", setMinStartTime);
    // run once on load
    setMinStartTime();
  })();

  /* ----------------------------
     Edit Booking page: availability check + update booking
     Targets: templates/edit_booking.html
     ---------------------------- */
  (function attachEditBookingLogic() {
    const editForm = document.getElementById("editBookingForm");
    const bookingIdEl = document.getElementById("booking_id");
    const checkBtn = document.getElementById("checkAvailabilityBtn");
    const availableRoomsContainer = document.getElementById("availableRooms");
    const roomSelect = document.getElementById("room");
    const messageBox = document.getElementById("message");
    const dateInput = document.getElementById("date");
    const startInput = document.getElementById("start_time");
    const endInput = document.getElementById("end_time");

    if (!editForm || !bookingIdEl) return;

    const bookingId = bookingIdEl.value;
    const currentRoom = "{{ booking.room_number }}" || roomSelect?.value; // used only when template rendering

    const today = new Date().toISOString().split("T")[0];
    if (dateInput) dateInput.min = today;

    const setMinStartTime = () => {
      if (!dateInput || !startInput) return;
      if (dateInput.value === today) {
        const now = new Date();
        const hours = String(now.getHours()).padStart(2, "0");
        const minutes = String(now.getMinutes()).padStart(2, "0");
        startInput.min = `${hours}:${minutes}`;
      } else {
        startInput.removeAttribute("min");
      }
    };

    const setMinEndTime = () => {
      if (!endInput || !startInput) return;
      endInput.min = hhmm(startInput.value);
    };

    if (dateInput) dateInput.addEventListener("change", setMinStartTime);
    if (startInput) startInput.addEventListener("change", setMinEndTime);
    setMinStartTime();
    setMinEndTime();

    async function checkAvailability() {
      if (!dateInput || !startInput || !endInput) return;
      const new_date = dateInput.value;
      const new_start = hhmm(startInput.value);
      const new_end = hhmm(endInput.value);

      if (!new_date || !new_start || !new_end) {
        availableRoomsContainer.style.color = "red";
        availableRoomsContainer.textContent = "Please select date and time.";
        return;
      }

      try {
        const res = await fetch(`/available-rooms/${bookingId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ new_date, new_start, new_end })
        });
        const data = await res.json();

        if (res.ok) {
          if (data.available_rooms && data.available_rooms.length) {
            availableRoomsContainer.style.color = "green";
            availableRoomsContainer.textContent = `Available Rooms: ${data.available_rooms.join(", ")}`;

            // refill dropdown
            roomSelect.innerHTML = "";
            const currentOption = document.createElement("option");
            currentOption.value = currentRoom || roomSelect.value;
            currentOption.textContent = `Current: ${currentOption.value}`;
            roomSelect.appendChild(currentOption);

            data.available_rooms.forEach(roomNumber => {
              if (String(roomNumber) !== String(currentOption.value)) {
                const option = document.createElement("option");
                option.value = roomNumber;
                option.textContent = `Room ${roomNumber}`;
                roomSelect.appendChild(option);
              }
            });
            roomSelect.size = Math.min(6, roomSelect.options.length);
          } else {
            availableRoomsContainer.style.color = "red";
            availableRoomsContainer.textContent = "No rooms available for the selected time.";
            roomSelect.innerHTML = "<option value=''>No rooms available</option>";
            roomSelect.size = 1;
          }
        } else {
          availableRoomsContainer.style.color = "red";
          availableRoomsContainer.textContent = data.detail || "Error checking availability.";
        }
      } catch (err) {
        availableRoomsContainer.style.color = "red";
        availableRoomsContainer.textContent = "Network error.";
      }
    }

    if (checkBtn) checkBtn.addEventListener("click", checkAvailability);

    editForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!dateInput || !startInput || !endInput || !roomSelect) return;

      const new_date = dateInput.value;
      const new_start = startInput.value;
      const new_end = endInput.value;
      const selected_room = roomSelect.value;

      if (!new_date || !new_start || !new_end || !selected_room) {
        messageBox.style.color = "red";
        messageBox.textContent = "Please fill all fields and select a room.";
        return;
      }

      if (new_end <= new_start) {
        messageBox.style.color = "red";
        messageBox.textContent = "End time must be after start time.";
        return;
      }

      messageBox.style.color = "black";
      messageBox.textContent = "Updating booking...";

      try {
        const res = await fetch(`/update-booking/${bookingId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ new_date, new_start, new_end, room: selected_room })
        });
        const data = await res.json();
        if (res.ok) {
          messageBox.style.color = "green";
          messageBox.textContent = data.message || "Booking updated successfully!";
          setTimeout(() => (window.location.href = "/history"), 1500);
        } else {
          messageBox.style.color = "red";
          messageBox.textContent = data.detail || "Failed to update booking.";
        }
      } catch (err) {
        messageBox.style.color = "red";
        messageBox.textContent = "Network error. Please try again.";
      }
    });
  })();

  /* ----------------------------
     History page: status updater & delete button
     Targets: templates/history.html
     ---------------------------- */
  (function attachHistoryLogic() {
    const bookingCards = document.querySelectorAll(".booking-card");
    if (!bookingCards || bookingCards.length === 0) return;

    function updateBookingStatus() {
      const now = new Date();
      const todayStr = now.toISOString().split("T")[0];
      bookingCards.forEach(card => {
        const startTimeStr = card.getAttribute("data-start");
        const endTimeStr = card.getAttribute("data-end");
        if (!startTimeStr || !endTimeStr) return;

        const startTime = new Date(startTimeStr);
        const endTime = new Date(endTimeStr);
        const bookingDateStr = startTimeStr.split("T")[0];
        const isToday = bookingDateStr === todayStr;

        const badge = card.querySelector(".badge");
        const editBtn = card.querySelector(".edit-btn");
        const deleteBtn = card.querySelector(".delete-btn");

        if (badge) badge.classList.remove("upcoming", "today", "past", "ongoing");

        if (now < startTime) {
          if (badge) { badge.innerText = isToday ? "Today" : "Upcoming"; badge.classList.add(isToday ? "today" : "upcoming"); }
          if ((startTime - now) > 30 * 60 * 1000) { if (editBtn) editBtn.style.display = "inline-block"; } else { if (editBtn) editBtn.style.display = "none"; }
          if ((startTime - now) > 60 * 60 * 1000) { if (deleteBtn) deleteBtn.style.display = "inline-block"; } else { if (deleteBtn) deleteBtn.style.display = "none"; }
        } else if (now >= startTime && now < endTime && isToday) {
          if (badge) { badge.classList.add("ongoing"); badge.innerText = "Ongoing"; }
          if (editBtn) editBtn.style.display = "none";
          if (deleteBtn) deleteBtn.style.display = "none";
          card.classList.remove("past-booking"); card.classList.add("ongoing-booking");
        } else if (now >= endTime) {
          if (badge) { badge.classList.add("past"); badge.innerText = "Past"; }
          if (editBtn) editBtn.style.display = "none";
          if (deleteBtn) deleteBtn.style.display = "none";
          card.classList.add("past-booking"); card.classList.remove("ongoing-booking");
        }
      });
    }

    updateBookingStatus();
    setInterval(updateBookingStatus, 1000);

    // delete buttons
    document.querySelectorAll(".delete-btn").forEach(button => {
      button.addEventListener("click", function (e) {
        e.preventDefault();
        const bookingId = this.getAttribute("data-booking-id");
        if (!bookingId) return;
        if (!confirm("Are you sure you want to delete this booking?")) return;

        fetch(`/delete-booking/${bookingId}`, { method: "DELETE", credentials: "include" })
          .then(res => {
            if (res.ok) {
              this.closest(".booking-card").remove();
            } else {
              alert("Failed to delete booking.");
            }
          })
          .catch(() => alert("Error deleting booking."));
      });
    });
  })();

  /* ----------------------------
     Register form client-side validation
     Targets: templates/register.html
     ---------------------------- */
  (function attachRegisterValidation() {
    const registerForm = document.querySelector("form[action='/register']");
    if (!registerForm) return;

    registerForm.addEventListener("submit", (e) => {
      const username = document.getElementById("username")?.value || "";
      const email = (document.getElementById("email")?.value || "").trim();
      const password = document.getElementById("password")?.value || "";

      if (!email.endsWith("@gmail.com")) {
        alert("Email must end with @gmail.com");
        e.preventDefault();
        return;
      }
      if (password.length < 8) {
        alert("Password must be at least 8 characters");
        e.preventDefault();
        return;
      }
      if (username.length < 6) {
        alert("Username must be at least 6 characters");
        e.preventDefault();
        return;
      }
    });
  })();

  /* ----------------------------
     Generic form-required check (fallback)
     Targets: any page with forms
     ---------------------------- */
  (function attachGenericFormGuard() {
    // keep small lightweight validation to avoid empty submissions
    document.querySelectorAll("form").forEach(form => {
      form.addEventListener("submit", (e) => {
        const requiredInputs = form.querySelectorAll("input[required], select[required], textarea[required]");
        for (const input of requiredInputs) {
          if (!input.value || !String(input.value).trim()) {
            alert(`Please fill out the ${input.name || input.id || "required"} field.`);
            input.focus();
            e.preventDefault();
            return false;
          }
        }
        return true;
      });
    });
  })();
});
