(function () {
  const form = document.getElementById("application-form");

  if (!form) {
    return;
  }

  const status = document.getElementById("form-status");
  const serviceInputs = Array.from(
    form.querySelectorAll('input[name="services"]'),
  );
  const fieldConfigs = {
    fullName: {
      message: "Indica tu nombre y apellido para identificar la solicitud.",
    },
    workEmail: {
      message:
        "Usa un email corporativo valido, por ejemplo nombre@empresa.com.",
      validate: function (value) {
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        const blockedDomains = [
          "gmail.com",
          "hotmail.com",
          "outlook.com",
          "yahoo.com",
        ];
        if (!emailPattern.test(value)) {
          return false;
        }
        const domain = value.split("@")[1].toLowerCase();
        return !blockedDomains.includes(domain);
      },
    },
    companyName: {
      message: "Indica la empresa que gestiona la operacion logistica.",
    },
    jobTitle: {
      message: "Indica tu cargo para contextualizar el proceso de decision.",
    },
    primaryMarket: {
      message: "Selecciona el mercado donde operas actualmente.",
    },
    monthlyOrders: {
      message:
        "Introduce una estimacion entre 100 y 1.000.000 pedidos mensuales.",
      validate: function (value) {
        const quantity = Number(value);
        return (
          Number.isFinite(quantity) && quantity >= 100 && quantity <= 1000000
        );
      },
    },
    launchTimeline: {
      message: "Selecciona el plazo aproximado de implementacion.",
    },
    operationSummary: {
      message: "Describe tu operacion actual con al menos 30 caracteres.",
      validate: function (value) {
        return value.length >= 30;
      },
    },
    consent: {
      message: "Debes aceptar el tratamiento de la informacion para continuar.",
      validate: function (_, element) {
        return element.checked;
      },
    },
  };

  function setErrorMessage(id, message) {
    const errorNode = document.getElementById(id + "-error");
    if (errorNode) {
      errorNode.textContent = message;
    }
  }

  function applyFieldState(element, isValid, message) {
    const usesTextStyle = element.matches("input, select, textarea");
    element.setAttribute("aria-invalid", String(!isValid));

    if (usesTextStyle) {
      element.classList.remove(
        "border-rose-400",
        "border-emerald-400",
        "ring-rose-300/40",
        "ring-emerald-300/30",
      );
      if (isValid) {
        element.classList.add("border-emerald-400", "ring-emerald-300/30");
      } else {
        element.classList.add("border-rose-400", "ring-rose-300/40");
      }
    }

    setErrorMessage(element.id, isValid ? "" : message);
  }

  function validateCheckboxGroup() {
    const isValid = serviceInputs.some(function (input) {
      return input.checked;
    });
    document.getElementById("services-error").textContent = isValid
      ? ""
      : "Selecciona al menos un servicio prioritario para evaluar tu caso.";
    serviceInputs.forEach(function (input) {
      input.setAttribute("aria-invalid", String(!isValid));
    });
    return isValid;
  }

  function validateField(id) {
    const element = document.getElementById(id);
    const config = fieldConfigs[id];
    const rawValue = element.type === "checkbox" ? "checked" : element.value;
    const value = typeof rawValue === "string" ? rawValue.trim() : rawValue;

    if (element.type !== "checkbox" && value === "") {
      applyFieldState(element, false, config.message);
      return false;
    }

    const isValid = config.validate ? config.validate(value, element) : true;
    applyFieldState(element, isValid, config.message);
    return isValid;
  }

  function clearFieldState(id) {
    const element = document.getElementById(id);
    element.setAttribute("aria-invalid", "false");
    if (element.matches("input, select, textarea")) {
      element.classList.remove(
        "border-rose-400",
        "border-emerald-400",
        "ring-rose-300/40",
        "ring-emerald-300/30",
      );
    }
    setErrorMessage(id, "");
  }

  function clearStatus() {
    status.className = "min-h-5 text-sm";
    status.textContent = "";
  }

  Object.keys(fieldConfigs).forEach(function (id) {
    const element = document.getElementById(id);
    const eventName = element.type === "checkbox" ? "change" : "blur";
    element.addEventListener(eventName, function () {
      validateField(id);
    });
  });

  serviceInputs.forEach(function (input) {
    input.addEventListener("change", validateCheckboxGroup);
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    clearStatus();

    let isFormValid = true;
    Object.keys(fieldConfigs).forEach(function (id) {
      if (!validateField(id)) {
        isFormValid = false;
      }
    });

    if (!validateCheckboxGroup()) {
      isFormValid = false;
    }

    if (!isFormValid) {
      status.className = "min-h-5 text-sm text-rose-300";
      status.textContent =
        "Corrige los errores del formulario antes de enviar la solicitud.";
      const firstInvalid = form.querySelector('[aria-invalid="true"]');
      if (firstInvalid) {
        firstInvalid.focus();
      }
      return;
    }

    status.className = "min-h-5 text-sm text-emerald-300";
    status.textContent =
      "Application enviada correctamente. El equipo de TrackFlow revisara tu caso y te contactara en menos de 24 horas laborables.";
    form.reset();
    Object.keys(fieldConfigs).forEach(clearFieldState);
    document.getElementById("services-error").textContent = "";
    serviceInputs.forEach(function (input) {
      input.setAttribute("aria-invalid", "false");
    });
  });

  form.addEventListener("reset", function () {
    clearStatus();
    window.requestAnimationFrame(function () {
      Object.keys(fieldConfigs).forEach(clearFieldState);
      document.getElementById("services-error").textContent = "";
      serviceInputs.forEach(function (input) {
        input.setAttribute("aria-invalid", "false");
      });
    });
  });
})();
