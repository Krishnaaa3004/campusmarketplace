// Password rules. Same as check_password_rules in campusmarket-backend/app/schemas/auth.py.
export const PASSWORD_MIN = 8
export const PASSWORD_HINT = 'At least 8 characters, with a letter and a number.'

export function passwordProblem(password = '') {
  if (password.length < PASSWORD_MIN) return `Use at least ${PASSWORD_MIN} characters.`
  if (password.length > 128) return 'Use at most 128 characters.'
  if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) return 'Include at least one letter and one number.'
  return null
}

// { password?, confirm? } inline errors for a "create password" pair of fields.
export function newPasswordErrors(password, confirm) {
  const errors = {}
  const problem = passwordProblem(password)
  if (problem) errors.password = problem
  if (!confirm) errors.confirm = 'Type the password again.'
  else if (password !== confirm) errors.confirm = "Passwords don't match."
  return errors
}
