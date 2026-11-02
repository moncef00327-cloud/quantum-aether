# configure-paypal.ps1
# نافذة Windows لإدخال سر PayPal وكلمة مرور لوحة الإدارة بدل خانات Terminal المخفية.
# القيم تُرسل إلى الخادم عبر SSH (مشفّرة) إلى deploy/configure.sh --stdin، ولا تُحفظ على هذا الجهاز.
# التشغيل:  pwsh -File deploy\configure-paypal.ps1
param([string]$Server = 'root@95.179.195.150')

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Show-Message($text) {
    [Windows.Forms.MessageBox]::Show($text, 'Quantum Aether') | Out-Null
}

$form = New-Object Windows.Forms.Form -Property @{
    Text = 'Quantum Aether - PayPal'
    ClientSize = New-Object Drawing.Size 480, 268
    StartPosition = 'CenterScreen'
    TopMost = $true
    FormBorderStyle = 'FixedDialog'
    MaximizeBox = $false
    MinimizeBox = $false
    RightToLeft = 'Yes'
    RightToLeftLayout = $true
    Font = New-Object Drawing.Font 'Segoe UI', 10
}

function Add-Field($label, $top) {
    $caption = New-Object Windows.Forms.Label -Property @{ Text = $label; Location = New-Object Drawing.Point 16, $top; AutoSize = $true }
    $box = New-Object Windows.Forms.TextBox -Property @{
        Location = New-Object Drawing.Point 16, ($top + 24); Width = 448; UseSystemPasswordChar = $true; RightToLeft = 'No'
    }
    $form.Controls.AddRange(@($caption, $box))
    $box
}

$secretBox = Add-Field 'سر PayPal (Live Secret) — الصقه بـ Ctrl+V' 12
$adminBox = Add-Field 'كلمة مرور لوحة الإدارة /admin — 8 أحرف على الأقل، أو اتركها فارغة' 72
$confirmBox = Add-Field 'تأكيد كلمة المرور' 132
$show = New-Object Windows.Forms.CheckBox -Property @{ Text = 'إظهار ما كتبته'; Location = New-Object Drawing.Point 16, 192; AutoSize = $true }
$show.Add_CheckedChanged({ foreach ($box in $secretBox, $adminBox, $confirmBox) { $box.UseSystemPasswordChar = -not $show.Checked } })
$ok = New-Object Windows.Forms.Button -Property @{ Text = 'حفظ وإرسال'; Location = New-Object Drawing.Point 16, 226; Width = 120; DialogResult = 'OK' }
$cancel = New-Object Windows.Forms.Button -Property @{ Text = 'إلغاء'; Location = New-Object Drawing.Point 144, 226; Width = 100; DialogResult = 'Cancel' }
$form.Controls.AddRange(@($show, $ok, $cancel))
$form.AcceptButton = $ok
$form.CancelButton = $cancel
$form.Add_Shown({ $form.Activate(); $secretBox.Focus() })

while ($true) {
    if ($form.ShowDialog() -ne [Windows.Forms.DialogResult]::OK) {
        Write-Host 'أُلغي. لم يتغير شيء.'
        exit 1
    }
    $secret = $secretBox.Text.Trim()
    $password = $adminBox.Text
    if (-not $secret -and -not $password) { Show-Message 'لم تُدخل شيئاً.'; continue }
    if ($password -ne $confirmBox.Text) { Show-Message 'كلمتا المرور غير متطابقتين.'; continue }
    if ($password -and $password.Length -lt 8) { Show-Message 'كلمة المرور أقصر من 8 أحرف.'; continue }
    break
}

# السطر الأول فارغ = إبقاء Client ID الحالي على الخادم.
$payload = "`n$secret`n$password`n"
$output = $payload | ssh -o BatchMode=yes $Server 'bash /var/www/quantum_saas/deploy/configure.sh --stdin' 2>&1
$code = $LASTEXITCODE
$text = ($output | ForEach-Object { "$_" }) -join "`n"
Write-Host $text
Show-Message $(if ($code -eq 0) { "تم الحفظ على الخادم.`n`n$text" } else { "لم يُحفظ شيء.`n`n$text" })
exit $code
