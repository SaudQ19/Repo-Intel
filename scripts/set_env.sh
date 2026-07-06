#!/bin/bash
# Load environment variables from the correct env file based on the argument.

ENV=${1:-development}
ENV_FILE=".env.${ENV}"

if [ -f "$ENV_FILE" ]; then
  # Export all variables from the env file, ignoring comments and empty lines
  while IFS= read -r line || [ -n "$line" ]; do
    # Skip comments and empty lines
    if [[ ! "$line" =~ ^# ]] && [[ ! -z "$line" ]]; then
      # Strip quotes if they exist and export
      clean_line=$(echo "$line" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
      export "$clean_line"
    fi
  done < "$ENV_FILE"
else
  echo "Warning: $ENV_FILE not found."
fi

# Execute the rest of the arguments if any
if [ $# -gt 1 ]; then
  shift
  exec "$@"
fi
