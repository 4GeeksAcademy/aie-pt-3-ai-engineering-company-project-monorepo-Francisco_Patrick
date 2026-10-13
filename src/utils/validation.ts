import type {
  Carrier,
  CarrierName,
  ClientContract,
  Country,
  ExecutiveKpiSnapshot,
  InventoryItem,
  ReturnRequest,
  Shipment,
  Warehouse,
  WarehouseCity,
} from "../types/entities.js";

export interface ValidationResult {
  isValid: boolean;
  errors: string[];
}

type FormFieldId =
  | "fullName"
  | "workEmail"
  | "companyName"
  | "jobTitle"
  | "primaryMarket"
  | "monthlyOrders"
  | "launchTimeline"
  | "operationSummary"
  | "consent";

interface FieldConfig {
  message: string;
  validate?: (
    value: string,
    element: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement,
  ) => boolean;
}

const allowedWarehouseByCountry: Record<Country, WarehouseCity[]> = {
  US: ["Los Angeles"],
  ES: ["Zaragoza"],
};

const allowedCarrierNames: CarrierName[] = [
  "UPS",
  "FedEx",
  "DHL",
  "MRW",
  "SEUR",
  "LocalCarrierUS",
  "LocalCarrierES",
  "CrossBorderExpress",
];

function isISODate(value: string): boolean {
  return Number.isNaN(Date.parse(value)) === false;
}

function pushIf(condition: boolean, error: string, errors: string[]): void {
  if (condition) {
    errors.push(error);
  }
}

export function validateWarehouse(warehouse: Warehouse): ValidationResult {
  const errors: string[] = [];
  pushIf(
    !allowedWarehouseByCountry[warehouse.country].includes(warehouse.city),
    "La ciudad del almacen no coincide con el pais operativo de TrackFlow.",
    errors,
  );
  pushIf(
    warehouse.operatorsCount <= 0,
    "operatorsCount debe ser mayor que 0.",
    errors,
  );
  pushIf(
    warehouse.managedBy.trim().length === 0,
    "managedBy no puede estar vacio.",
    errors,
  );
  return { isValid: errors.length === 0, errors };
}

export function validateInventoryItem(item: InventoryItem): ValidationResult {
  const errors: string[] = [];
  pushIf(item.stockUnits < 0, "stockUnits no puede ser negativo.", errors);
  pushIf(
    item.lowStockThreshold < 0,
    "lowStockThreshold no puede ser negativo.",
    errors,
  );
  pushIf(
    !isISODate(item.updatedAtISO),
    "updatedAtISO debe ser una fecha ISO valida.",
    errors,
  );
  return { isValid: errors.length === 0, errors };
}

export function validateCarrier(carrier: Carrier): ValidationResult {
  const errors: string[] = [];
  pushIf(
    !allowedCarrierNames.includes(carrier.name),
    "carrier.name no esta dentro del catalogo de 8 transportistas de TrackFlow.",
    errors,
  );
  pushIf(
    carrier.countries.length === 0,
    "El transportista debe operar al menos en un pais.",
    errors,
  );
  pushIf(
    carrier.onTimeRate < 0 || carrier.onTimeRate > 1,
    "onTimeRate debe estar entre 0 y 1.",
    errors,
  );
  pushIf(
    carrier.incidentsPer100Shipments < 0,
    "incidentsPer100Shipments no puede ser negativo.",
    errors,
  );
  pushIf(
    carrier.costPerKgEUR < 0,
    "costPerKgEUR no puede ser negativo.",
    errors,
  );
  return { isValid: errors.length === 0, errors };
}

export function validateShipment(shipment: Shipment): ValidationResult {
  const errors: string[] = [];
  pushIf(shipment.weightKg <= 0, "weightKg debe ser mayor que 0.", errors);
  pushIf(
    shipment.operationalCostEUR < 0,
    "operationalCostEUR no puede ser negativo.",
    errors,
  );
  pushIf(
    !isISODate(shipment.shippedAtISO),
    "shippedAtISO debe ser una fecha ISO valida.",
    errors,
  );
  pushIf(
    !allowedCarrierNames.includes(shipment.carrierName),
    "carrierName debe existir en el catalogo de transportistas de TrackFlow.",
    errors,
  );
  return { isValid: errors.length === 0, errors };
}

export function validateReturnRequest(
  returnRequest: ReturnRequest,
): ValidationResult {
  const errors: string[] = [];
  pushIf(
    returnRequest.reason.trim().length === 0,
    "reason no puede estar vacio.",
    errors,
  );
  pushIf(
    !isISODate(returnRequest.requestedAtISO),
    "requestedAtISO debe ser una fecha ISO valida.",
    errors,
  );
  if (returnRequest.inspectedAtISO !== null) {
    pushIf(
      !isISODate(returnRequest.inspectedAtISO),
      "inspectedAtISO debe ser null o una fecha ISO valida.",
      errors,
    );
  }
  if (returnRequest.decision !== "manual_review") {
    pushIf(
      returnRequest.inspectedAtISO === null,
      "Las devoluciones aprobadas o rechazadas deben incluir inspectedAtISO.",
      errors,
    );
  }
  return { isValid: errors.length === 0, errors };
}

export function validateClientContract(
  contract: ClientContract,
): ValidationResult {
  const errors: string[] = [];
  const start = Date.parse(contract.startsAtISO);
  const end = Date.parse(contract.endsAtISO);

  pushIf(
    Number.isNaN(start) || Number.isNaN(end),
    "Las fechas del contrato deben ser ISO validas.",
    errors,
  );
  if (!Number.isNaN(start) && !Number.isNaN(end)) {
    const diffDays = Math.round((end - start) / (1000 * 60 * 60 * 24));
    pushIf(
      diffDays < 365 || diffDays > 366,
      "Los contratos de TrackFlow son anuales (365-366 dias).",
      errors,
    );
  }
  pushIf(
    contract.annualContractValueEUR <= 0,
    "annualContractValueEUR debe ser mayor que 0.",
    errors,
  );
  pushIf(
    contract.renewalRiskScore < 0 || contract.renewalRiskScore > 100,
    "renewalRiskScore debe estar entre 0 y 100.",
    errors,
  );
  return { isValid: errors.length === 0, errors };
}

export function validateExecutiveKpiSnapshot(
  snapshot: ExecutiveKpiSnapshot,
): ValidationResult {
  const errors: string[] = [];
  pushIf(
    snapshot.shipmentsVolume < 0,
    "shipmentsVolume no puede ser negativo.",
    errors,
  );
  pushIf(
    snapshot.onTimeDeliveryRate < 0 || snapshot.onTimeDeliveryRate > 1,
    "onTimeDeliveryRate debe estar entre 0 y 1.",
    errors,
  );
  pushIf(
    snapshot.operationalCostEUR < 0,
    "operationalCostEUR no puede ser negativo.",
    errors,
  );
  pushIf(
    snapshot.returnsRate < 0.18 || snapshot.returnsRate > 0.25,
    "returnsRate debe reflejar el rango observado por TrackFlow (0.18-0.25).",
    errors,
  );
  pushIf(
    snapshot.customerSatisfactionScore < 0 || snapshot.customerSatisfactionScore > 100,
    "customerSatisfactionScore debe estar entre 0 y 100.",
    errors,
  );
  pushIf(
    !isISODate(snapshot.generatedAtISO),
    "generatedAtISO debe ser una fecha ISO valida.",
    errors,
  );
  return { isValid: errors.length === 0, errors };
}

export function validateAllTrackFlowData(input: {
  warehouses: Warehouse[];
  inventoryItems: InventoryItem[];
  carriers: Carrier[];
  shipments: Shipment[];
  returnRequests: ReturnRequest[];
  clientContracts: ClientContract[];
  executiveKpis: ExecutiveKpiSnapshot[];
}): ValidationResult {
  const errors: string[] = [];

  input.warehouses.forEach((item: Warehouse, index: number) => {
    const result = validateWarehouse(item);
    result.errors.forEach((error: string) => {
      errors.push(`warehouses[${index}]: ${error}`);
    });
  });

  input.inventoryItems.forEach((item: InventoryItem, index: number) => {
    const result = validateInventoryItem(item);
    result.errors.forEach((error: string) => {
      errors.push(`inventoryItems[${index}]: ${error}`);
    });
  });

  input.carriers.forEach((item: Carrier, index: number) => {
    const result = validateCarrier(item);
    result.errors.forEach((error: string) => {
      errors.push(`carriers[${index}]: ${error}`);
    });
  });

  input.shipments.forEach((item: Shipment, index: number) => {
    const result = validateShipment(item);
    result.errors.forEach((error: string) => {
      errors.push(`shipments[${index}]: ${error}`);
    });
  });

  input.returnRequests.forEach((item: ReturnRequest, index: number) => {
    const result = validateReturnRequest(item);
    result.errors.forEach((error: string) => {
      errors.push(`returnRequests[${index}]: ${error}`);
    });
  });

  input.clientContracts.forEach((item: ClientContract, index: number) => {
    const result = validateClientContract(item);
    result.errors.forEach((error: string) => {
      errors.push(`clientContracts[${index}]: ${error}`);
    });
  });

  input.executiveKpis.forEach((item: ExecutiveKpiSnapshot, index: number) => {
    const result = validateExecutiveKpiSnapshot(item);
    result.errors.forEach((error: string) => {
      errors.push(`executiveKpis[${index}]: ${error}`);
    });
  });

  return { isValid: errors.length === 0, errors };
}

function getRequiredElementById<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (element === null) {
    throw new Error(`Elemento requerido no encontrado: ${id}`);
  }
  return element as T;
}

function bootstrapApplicationFormValidation(): void {
  if (typeof document === "undefined") {
    return;
  }

  const form = document.getElementById("application-form");

  if (!(form instanceof HTMLFormElement)) {
    return;
  }

  const status = getRequiredElementById<HTMLElement>("form-status");

  const serviceInputs = Array.from(
    form.querySelectorAll<HTMLInputElement>('input[name="services"]'),
  );

  const fieldConfigs: Record<FormFieldId, FieldConfig> = {
    fullName: {
      message: "Indica tu nombre y apellido para identificar la solicitud.",
    },
    workEmail: {
      message:
        "Usa un email corporativo valido, por ejemplo nombre@empresa.com.",
      validate: (value: string) => {
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        const blockedDomains: string[] = [
          "gmail.com",
          "hotmail.com",
          "outlook.com",
          "yahoo.com",
        ];
        if (!emailPattern.test(value)) {
          return false;
        }
        const domain = value.split("@")[1]?.toLowerCase() ?? "";
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
      validate: (value: string) => {
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
      validate: (value: string) => {
        return value.length >= 30;
      },
    },
    consent: {
      message: "Debes aceptar el tratamiento de la informacion para continuar.",
      validate: (_: string, element) => {
        return element instanceof HTMLInputElement && element.checked;
      },
    },
  };

  function setErrorMessage(id: string, message: string): void {
    const errorNode = document.getElementById(`${id}-error`);
    if (errorNode instanceof HTMLElement) {
      errorNode.textContent = message;
    }
  }

  function applyFieldState(
    element: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement,
    isValid: boolean,
    message: string,
  ): void {
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

  function validateCheckboxGroup(): boolean {
    const isValid = serviceInputs.some((input: HTMLInputElement) => {
      return input.checked;
    });
    const serviceError = document.getElementById("services-error");
    if (serviceError instanceof HTMLElement) {
      serviceError.textContent = isValid
        ? ""
        : "Selecciona al menos un servicio prioritario para evaluar tu caso.";
    }
    serviceInputs.forEach((input: HTMLInputElement) => {
      input.setAttribute("aria-invalid", String(!isValid));
    });
    return isValid;
  }

  function validateField(id: FormFieldId): boolean {
    const element = getRequiredElementById<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >(id);
    const config = fieldConfigs[id];
    const rawValue =
      element instanceof HTMLInputElement && element.type === "checkbox"
        ? "checked"
        : element.value;
    const value = typeof rawValue === "string" ? rawValue.trim() : rawValue;

    if (
      !(element instanceof HTMLInputElement && element.type === "checkbox") &&
      value === ""
    ) {
      applyFieldState(element, false, config.message);
      return false;
    }

    const isValid = config.validate ? config.validate(value, element) : true;
    applyFieldState(element, isValid, config.message);
    return isValid;
  }

  function clearFieldState(id: FormFieldId): void {
    const element = getRequiredElementById<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >(id);
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

  function clearStatus(): void {
    status.className = "min-h-5 text-sm";
    status.textContent = "";
  }

  (Object.keys(fieldConfigs) as FormFieldId[]).forEach((id: FormFieldId) => {
    const element = getRequiredElementById<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >(id);
    const eventName =
      element instanceof HTMLInputElement && element.type === "checkbox"
        ? "change"
        : "blur";
    element.addEventListener(eventName, () => {
      validateField(id);
    });
  });

  serviceInputs.forEach((input: HTMLInputElement) => {
    input.addEventListener("change", validateCheckboxGroup);
  });

  form.addEventListener("submit", (event: SubmitEvent) => {
    event.preventDefault();
    clearStatus();

    let isFormValid = true;
    (Object.keys(fieldConfigs) as FormFieldId[]).forEach((id: FormFieldId) => {
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
      const firstInvalid = form.querySelector<HTMLElement>('[aria-invalid="true"]');
      if (firstInvalid instanceof HTMLElement) {
        firstInvalid.focus();
      }
      return;
    }

    status.className = "min-h-5 text-sm text-emerald-300";
    status.textContent =
      "Application enviada correctamente. El equipo de TrackFlow revisara tu caso y te contactara en menos de 24 horas laborables.";
    form.reset();
    (Object.keys(fieldConfigs) as FormFieldId[]).forEach(clearFieldState);
    const serviceError = document.getElementById("services-error");
    if (serviceError instanceof HTMLElement) {
      serviceError.textContent = "";
    }
    serviceInputs.forEach((input: HTMLInputElement) => {
      input.setAttribute("aria-invalid", "false");
    });
  });

  form.addEventListener("reset", () => {
    clearStatus();
    window.requestAnimationFrame(() => {
      (Object.keys(fieldConfigs) as FormFieldId[]).forEach(clearFieldState);
      const serviceError = document.getElementById("services-error");
      if (serviceError instanceof HTMLElement) {
        serviceError.textContent = "";
      }
      serviceInputs.forEach((input: HTMLInputElement) => {
        input.setAttribute("aria-invalid", "false");
      });
    });
  });
}

bootstrapApplicationFormValidation();
