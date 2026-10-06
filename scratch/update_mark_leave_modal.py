import os

file_path = r"C:\Users\disha\TimeSheet_Frontend\src\components\employee\MarkLeaveModal.tsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add currentYear, minDate, maxDate
target_hook = "const [validationError, setValidationError] = useState<string | null>(null);"
replacement_hook = """const [validationError, setValidationError] = useState<string | null>(null);

  // Current calendar year bounds
  const currentYear = new Date().getFullYear();
  const minDate = `${currentYear}-01-01`;
  const maxDate = `${currentYear}-12-31`;"""

content = content.replace(target_hook, replacement_hook)

# 2. Add validation in validateAndBuild for full_day
target_fd_val = """      if (startDate > endDate) {
        setValidationError('End Date cannot be earlier than Start Date.');
        return null;
      }"""

replacement_fd_val = """      if (startDate > endDate) {
        setValidationError('End Date cannot be earlier than Start Date.');
        return null;
      }

      const sYear = new Date(startDate).getFullYear();
      const eYear = new Date(endDate).getFullYear();
      if (sYear !== currentYear || eYear !== currentYear) {
        setValidationError(`Leaves can only be marked for the current calendar year (${currentYear}). Requests for previous or future years are not allowed.`);
        return null;
      }"""

content = content.replace(target_fd_val, replacement_fd_val)

# 3. Add validation in validateAndBuild for custom
target_custom_val = """    const payload: MarkLeavePayload = {
      leave_duration_type: customSubType,
      leave_date: singleDate,
      reason: reason.trim() || 'Marked from timesheet',
    };"""

replacement_custom_val = """    const selYear = new Date(singleDate).getFullYear();
    if (selYear !== currentYear) {
      setValidationError(`Leaves can only be marked for the current calendar year (${currentYear}). Requests for previous or future years are not allowed.`);
      return null;
    }

    const payload: MarkLeavePayload = {
      leave_duration_type: customSubType,
      leave_date: singleDate,
      reason: reason.trim() || 'Marked from timesheet',
    };"""

content = content.replace(target_custom_val, replacement_custom_val)

# 4. Add min & max to inputs
# Start Date input
content = content.replace(
    '<input\n                      type="date"\n                      value={startDate}',
    '<input\n                      type="date"\n                      min={minDate}\n                      max={maxDate}\n                      value={startDate}'
)

# End Date input
content = content.replace(
    '<input\n                      type="date"\n                      value={endDate}\n                      min={startDate}',
    '<input\n                      type="date"\n                      value={endDate}\n                      min={startDate}\n                      max={maxDate}'
)

# Single Date input
content = content.replace(
    '<input\n                  type="date"\n                  value={singleDate}',
    '<input\n                  type="date"\n                  min={minDate}\n                  max={maxDate}\n                  value={singleDate}'
)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("MarkLeaveModal.tsx updated successfully.")
