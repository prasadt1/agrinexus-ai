#!/bin/bash

# Configuration
IMAGE_PATH="docs/visuals/agrinexus-dashboard-enhanced.png"

echo "🔍 Verifying Dashboard Screenshot"
echo "=================================="
echo ""

# Check if file exists
if [ ! -f "${IMAGE_PATH}" ]; then
    echo "❌ Image not found: ${IMAGE_PATH}"
    echo ""
    echo "Please save the dashboard screenshot to this location."
    echo "See ADD-DASHBOARD-IMAGE.md for instructions."
    exit 1
fi

echo "✅ Image exists: ${IMAGE_PATH}"
echo ""

# Check file size
FILE_SIZE=$(du -h "${IMAGE_PATH}" | cut -f1)
FILE_SIZE_BYTES=$(stat -f%z "${IMAGE_PATH}" 2>/dev/null || stat -c%s "${IMAGE_PATH}" 2>/dev/null)

echo "📊 Image Details:"
echo "   Size: ${FILE_SIZE} (${FILE_SIZE_BYTES} bytes)"

# Check if size is reasonable (200KB - 5MB)
if [ "${FILE_SIZE_BYTES}" -lt 200000 ]; then
    echo "   ⚠️  Warning: File seems small (<200KB). Might be low quality."
elif [ "${FILE_SIZE_BYTES}" -gt 5000000 ]; then
    echo "   ⚠️  Warning: File is large (>5MB). Consider optimizing."
else
    echo "   ✅ Size looks good (200KB - 5MB)"
fi

# Check file type
FILE_TYPE=$(file -b "${IMAGE_PATH}")
echo "   Type: ${FILE_TYPE}"

if [[ "${FILE_TYPE}" == *"PNG"* ]]; then
    echo "   ✅ Format is PNG (recommended)"
elif [[ "${FILE_TYPE}" == *"JPEG"* ]] || [[ "${FILE_TYPE}" == *"JPG"* ]]; then
    echo "   ⚠️  Format is JPEG (PNG recommended for dashboards)"
else
    echo "   ❌ Unexpected format: ${FILE_TYPE}"
fi

# Check git status
echo ""
echo "📝 Git Status:"
if git ls-files --error-unmatch "${IMAGE_PATH}" > /dev/null 2>&1; then
    echo "   ✅ File is tracked by git"
    
    # Check if modified
    if git diff --quiet "${IMAGE_PATH}"; then
        echo "   ✅ No uncommitted changes"
    else
        echo "   ⚠️  File has uncommitted changes"
        echo ""
        echo "   To commit:"
        echo "   git add ${IMAGE_PATH}"
        echo "   git commit -m 'Add enhanced CloudWatch dashboard screenshot'"
    fi
else
    echo "   ⚠️  File is not tracked by git"
    echo ""
    echo "   To add to git:"
    echo "   git add ${IMAGE_PATH}"
    echo "   git commit -m 'Add enhanced CloudWatch dashboard screenshot for article'"
fi

echo ""
echo "🖼️  To view the image:"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "   open ${IMAGE_PATH}"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "   xdg-open ${IMAGE_PATH}"
else
    echo "   (Open ${IMAGE_PATH} in your image viewer)"
fi

echo ""
echo "✅ Verification complete!"
