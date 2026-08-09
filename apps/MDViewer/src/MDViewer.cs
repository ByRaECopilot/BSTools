// MDViewer - visor de Markdown de solo lectura, con WebView2.
//
// Parte de BSTools - https://www.byraesoftware.com
// Licencia CC0 1.0 (dominio publico).
//
// Diseno (resumen):
// - Instancia unica hibrida: la primera ejecucion crea el proceso, un Mutex
//   con nombre y un NamedPipeServerStream. Una segunda ejecucion (doble clic
//   en otro .md) manda la ruta por el pipe y termina de inmediato; el
//   proceso vivo abre una ventana nueva reutilizando el MISMO
//   CoreWebView2Environment, asi el segundo archivo abre casi al instante.
// - El HTML del visor (assets\viewer.html) viene embebido como recurso del
//   ejecutable: no se navega a un archivo en disco, se usa NavigateToString.
// - Solo lectura: no hay edicion ni guardado del .md. La unica escritura a
//   disco es el PDF que el usuario pide exportar explicitamente.
// - Compilado con csc.exe de .NET Framework (sin SDK), limitado a C# 5:
//   nada de interpolacion de cadenas, "?.", "nameof" ni expresiones-cuerpo.
//
// Compilar con build.ps1 (raiz de esta carpeta).

using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Pipes;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Win32;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace BSTools.MDViewer
{
    /// <summary>
    /// Punto de entrada. Gestiona la instancia unica (Mutex + pipe con
    /// nombre) y el CoreWebView2Environment compartido por todas las
    /// ventanas del proceso.
    /// </summary>
    internal static class Program
    {
        private const string MutexName = "BSTools_MDViewer_SingleInstance";
        private const string PipeName = "BSTools_MDViewer_Pipe";

        private static MultiFormApplicationContext _appContext;
        private static Form _marshalForm;
        private static Task<CoreWebView2Environment> _environmentTask;

        // NOTA DE RENDIMIENTO (medido, no adivinado): el camino desechable
        // (segunda instancia que solo manda la ruta por el pipe y sale) se
        // media en ~1000 ms con "Start-Process -Wait" de PowerShell. Se
        // investigo a fondo (Stopwatch dentro de Main, Environment.Exit(0)
        // en vez de "return" para descartar el teardown del AppDomain, y
        // separar esta rama en un metodo [MethodImpl(NoInlining)] aparte
        // para descartar que el JIT cargara System.Windows.Forms solo por
        // resolver los tipos que aparecen en el cuerpo de Main). Ninguna de
        // esas hipotesis cambio el numero. La causa real: "Start-Process
        // -Wait" tiene ~1000 ms de sobrecarga propia en PowerShell, medible
        // hasta en un .exe vacio sin una sola linea de codigo (confirmado
        // comparando contra Process.Start+WaitForExit, que es el mismo
        // mecanismo que usa el Explorador al abrir un archivo por doble
        // clic via ShellExecute: ese camino mide ~50-60 ms consistentes,
        // con o sin las "optimizaciones" de arriba). No se dejan cambios de
        // estructura en Main: no hay nada que arreglar en el codigo.
        [STAThread]
        private static void Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            string initialPath = NormalizeArg(args);

            bool createdNew;
            Mutex mutex = new Mutex(true, MutexName, out createdNew);

            if (!createdNew)
            {
                SendPathToRunningInstance(initialPath);
                mutex.Close();
                return;
            }

            // Ventana invisible que nunca se muestra: solo existe para tener
            // un handle de Win32 en el hilo de UI, y poder usar BeginInvoke
            // desde el hilo del pipe (que corre en un hilo aparte).
            _marshalForm = new Form();
            _marshalForm.ShowInTaskbar = false;
            IntPtr forceHandleCreation = _marshalForm.Handle;

            _appContext = new MultiFormApplicationContext();

            Thread pipeThread = new Thread(PipeServerLoop);
            pipeThread.IsBackground = true;
            pipeThread.Name = "MDViewer-Pipe";
            pipeThread.Start();

            ViewerForm firstForm = new ViewerForm(initialPath);
            _appContext.TrackForm(firstForm);
            firstForm.Show();

            Application.Run(_appContext);

            mutex.Close();
        }

        /// <summary>
        /// Entorno de WebView2 compartido por todas las ventanas del
        /// proceso. Se crea una sola vez (la parte lenta del arranque); las
        /// ventanas siguientes lo reutilizan y abren casi al instante.
        /// Solo se llama desde el hilo de UI.
        /// </summary>
        internal static Task<CoreWebView2Environment> GetEnvironmentAsync()
        {
            if (_environmentTask == null)
            {
                string userDataFolder = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "BSTools", "MDViewer", "WebView2");
                _environmentTask = CoreWebView2Environment.CreateAsync(null, userDataFolder, null);
            }
            return _environmentTask;
        }

        private static string NormalizeArg(string[] args)
        {
            if (args.Length == 0 || string.IsNullOrWhiteSpace(args[0]))
            {
                return null;
            }
            try
            {
                return Path.GetFullPath(args[0]);
            }
            catch
            {
                return args[0];
            }
        }

        private static void PipeServerLoop()
        {
            while (true)
            {
                try
                {
                    using (NamedPipeServerStream pipeServer = new NamedPipeServerStream(
                        PipeName, PipeDirection.In, 1, PipeTransmissionMode.Byte, PipeOptions.None))
                    {
                        pipeServer.WaitForConnection();
                        using (StreamReader reader = new StreamReader(pipeServer, Encoding.UTF8))
                        {
                            string path = reader.ReadLine();
                            OpenPathOnUiThread(path);
                        }
                    }
                }
                catch (ObjectDisposedException)
                {
                    return;
                }
                catch (IOException)
                {
                    // El cliente se desconecto antes de tiempo: se reintenta
                    // con la siguiente conexion.
                }
            }
        }

        private static void OpenPathOnUiThread(string path)
        {
            if (_marshalForm == null || _marshalForm.IsDisposed)
            {
                return;
            }

            _marshalForm.BeginInvoke(new Action(delegate
            {
                ViewerForm form = new ViewerForm(string.IsNullOrEmpty(path) ? null : path);
                _appContext.TrackForm(form);
                form.Show();
                form.Activate();
            }));
        }

        private static void SendPathToRunningInstance(string path)
        {
            try
            {
                using (NamedPipeClientStream pipeClient = new NamedPipeClientStream(
                    ".", PipeName, PipeDirection.Out))
                {
                    pipeClient.Connect(3000);
                    using (StreamWriter writer = new StreamWriter(pipeClient, Encoding.UTF8))
                    {
                        writer.AutoFlush = true;
                        writer.WriteLine(path == null ? string.Empty : path);
                    }
                }
            }
            catch (Exception)
            {
                // La instancia principal no respondio a tiempo. No hay una
                // buena recuperacion desde una instancia secundaria; se sale
                // en silencio en vez de arrancar un segundo proceso que
                // competiria por el mismo Mutex.
            }
        }
    }

    /// <summary>
    /// ApplicationContext que mantiene el bucle de mensajes vivo mientras
    /// haya al menos una ventana abierta, y lo cierra cuando se cierra la
    /// ultima (con instancia unica hibrida puede haber varias ventanas a la
    /// vez, cada una con su propio archivo).
    /// </summary>
    internal sealed class MultiFormApplicationContext : ApplicationContext
    {
        private int _openForms;

        public void TrackForm(Form form)
        {
            _openForms = _openForms + 1;
            form.FormClosed += delegate
            {
                _openForms = _openForms - 1;
                if (_openForms <= 0)
                {
                    ExitThread();
                }
            };
        }
    }

    /// <summary>
    /// Ventana del visor: una por archivo abierto. Aloja el WebView2 con el
    /// HTML embebido, vigila el archivo en disco para recargar en vivo, y
    /// resuelve la exportacion a PDF (con carga diferida: nada de eso se
    /// toca hasta que el usuario pulsa el boton en el HTML).
    /// </summary>
    internal sealed class ViewerForm : Form
    {
        private const string ViewerResourceName = "MDViewer.Viewer.html";
        private const string IconResourceName = "MDViewer.Icon.ico";

        private readonly WebView2 _webView;
        private readonly MenuStrip _menu;
        private string _currentFilePath;
        private FileSystemWatcher _watcher;
        private System.Windows.Forms.Timer _debounceTimer;
        private bool _viewerReady;

        public ViewerForm(string initialPath)
        {
            _currentFilePath = initialPath;

            Text = "MDViewer";
            BackColor = Color.White;
            Width = 960;
            Height = 720;
            StartPosition = FormStartPosition.CenterScreen;

            Icon windowIcon = LoadEmbeddedIcon();
            if (windowIcon != null)
            {
                Icon = windowIcon;
            }

            // Orden de alta importante para el docking: primero el control
            // que rellena (Fill), despues los que se anclan a un borde
            // (Top); si se anaden al reves, el menu queda tapado.
            _webView = new WebView2();
            _webView.Dock = DockStyle.Fill;
            _webView.DefaultBackgroundColor = Color.White;
            Controls.Add(_webView);

            _menu = BuildMenu();
            _menu.Dock = DockStyle.Top;
            Controls.Add(_menu);
            MainMenuStrip = _menu;

            Load += OnLoadAsync;
            FormClosed += OnFormClosed;
        }

        private MenuStrip BuildMenu()
        {
            MenuStrip menu = new MenuStrip();
            ToolStripMenuItem root = new ToolStripMenuItem("MDViewer");

            ToolStripMenuItem associate = new ToolStripMenuItem("Asociar .md con MDViewer");
            associate.Click += delegate
            {
                FileAssociation.Associate();
                MessageBox.Show(this,
                    "Archivos .md asociados con MDViewer.",
                    "MDViewer", MessageBoxButtons.OK, MessageBoxIcon.Information);
            };

            ToolStripMenuItem disassociate = new ToolStripMenuItem("Quitar asociacion .md");
            disassociate.Click += delegate
            {
                FileAssociation.Disassociate();
                MessageBox.Show(this,
                    "Asociacion quitada. Si Windows ya recordaba MDViewer como app por " +
                    "defecto (UserChoice), el dialogo \"Abrir con\" puede seguir " +
                    "apareciendo hasta que elijas otra app a mano.",
                    "MDViewer", MessageBoxButtons.OK, MessageBoxIcon.Information);
            };

            ToolStripMenuItem exit = new ToolStripMenuItem("Salir");
            exit.Click += delegate { Close(); };

            root.DropDownItems.Add(associate);
            root.DropDownItems.Add(disassociate);
            root.DropDownItems.Add(new ToolStripSeparator());
            root.DropDownItems.Add(exit);

            menu.Items.Add(root);
            return menu;
        }

        private async void OnLoadAsync(object sender, EventArgs e)
        {
            // Solo pregunta una vez en la vida del programa (flag en el
            // registro); en ventanas siguientes es un no-op instantaneo.
            FileAssociation.MaybeOfferAssociation(this);

            if (string.IsNullOrEmpty(_currentFilePath) || !File.Exists(_currentFilePath))
            {
                if (!string.IsNullOrEmpty(_currentFilePath))
                {
                    MessageBox.Show(this,
                        "No se encontro el archivo:\n" + _currentFilePath,
                        "MDViewer", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                }
                _currentFilePath = PromptForFile();
                if (_currentFilePath == null)
                {
                    Close();
                    return;
                }
            }

            try
            {
                CoreWebView2Environment environment = await Program.GetEnvironmentAsync();
                await _webView.EnsureCoreWebView2Async(environment);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this,
                    "No se pudo iniciar WebView2:\n" + ex.Message,
                    "MDViewer", MessageBoxButtons.OK, MessageBoxIcon.Error);
                Close();
                return;
            }

            _webView.CoreWebView2.WebMessageReceived += OnWebMessageReceived;
            _webView.CoreWebView2.NavigationCompleted += OnNavigationCompleted;

            string html = LoadEmbeddedViewerHtml();
            _webView.CoreWebView2.NavigateToString(html);

            UpdateTitle();
            StartWatcher(_currentFilePath);
        }

        private async void OnNavigationCompleted(object sender, CoreWebView2NavigationCompletedEventArgs e)
        {
            if (!e.IsSuccess)
            {
                MessageBox.Show(this,
                    "No se pudo cargar el visor (assets\\viewer.html).",
                    "MDViewer", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            _viewerReady = true;
            await RenderCurrentFileAsync();
        }

        private async Task RenderCurrentFileAsync()
        {
            if (!_viewerReady || string.IsNullOrEmpty(_currentFilePath))
            {
                return;
            }

            string markdown;
            try
            {
                markdown = ReadFileWithRetry(_currentFilePath);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this,
                    "No se pudo leer el archivo:\n" + ex.Message,
                    "MDViewer", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string title = Path.GetFileName(_currentFilePath);
            string script = "window.MDV.render(" + JsonEncodeString(markdown) + ", " +
                JsonEncodeString(title) + ");";
            await _webView.CoreWebView2.ExecuteScriptAsync(script);
        }

        private static string ReadFileWithRetry(string path)
        {
            // Un editor puede tener el archivo bloqueado un instante
            // mientras guarda; unos pocos reintentos cortos lo resuelven.
            int attempts = 0;
            while (true)
            {
                try
                {
                    return File.ReadAllText(path, Encoding.UTF8);
                }
                catch (IOException)
                {
                    attempts = attempts + 1;
                    if (attempts >= 5)
                    {
                        throw;
                    }
                    Thread.Sleep(100);
                }
            }
        }

        private const string OpenLinkPrefix = "open-link:";

        private async void OnWebMessageReceived(object sender, CoreWebView2WebMessageReceivedEventArgs e)
        {
            string message = null;
            try
            {
                message = e.TryGetWebMessageAsString();
            }
            catch (Exception)
            {
                return;
            }

            if (message == "export-pdf")
            {
                await ExportPdfAsync();
            }
            else if (message != null && message.StartsWith(OpenLinkPrefix, StringComparison.Ordinal))
            {
                string href = message.Substring(OpenLinkPrefix.Length);
                OpenExternalLink(href);
            }
        }

        /// <summary>
        /// Abre un enlace del documento renderizado en el navegador por
        /// defecto del sistema. El .md es contenido no confiable: solo se
        /// permiten los esquemas http, https y mailto. Cualquier otra cosa
        /// (file://, rutas UNC, esquemas raros) se ignora en silencio, para
        /// que Process.Start no se convierta en un vector de ejecucion.
        /// </summary>
        private static void OpenExternalLink(string href)
        {
            Uri uri;
            if (!Uri.TryCreate(href, UriKind.Absolute, out uri))
            {
                return;
            }

            string scheme = uri.Scheme.ToLowerInvariant();
            if (scheme != "http" && scheme != "https" && scheme != "mailto")
            {
                return;
            }

            try
            {
                ProcessStartInfo startInfo = new ProcessStartInfo(uri.AbsoluteUri);
                startInfo.UseShellExecute = true;
                Process.Start(startInfo);
            }
            catch (Exception)
            {
                // Un fallo al abrir el navegador no puede tumbar el visor.
            }
        }

        /// <summary>
        /// Carga diferida: SaveFileDialog y PrintToPdfAsync solo se tocan
        /// aqui, al recibir el mensaje del boton. Nada de esto se prepara
        /// en el arranque.
        /// </summary>
        private async Task ExportPdfAsync()
        {
            using (SaveFileDialog dialog = new SaveFileDialog())
            {
                dialog.Filter = "PDF (*.pdf)|*.pdf";
                dialog.Title = "MDViewer - Exportar a PDF";
                string baseName = string.IsNullOrEmpty(_currentFilePath)
                    ? "documento"
                    : Path.GetFileNameWithoutExtension(_currentFilePath);
                dialog.FileName = baseName + ".pdf";

                if (dialog.ShowDialog(this) != DialogResult.OK)
                {
                    return;
                }

                bool ok;
                try
                {
                    CoreWebView2PrintSettings settings = _webView.CoreWebView2.Environment.CreatePrintSettings();
                    ok = await _webView.CoreWebView2.PrintToPdfAsync(dialog.FileName, settings);
                }
                catch (Exception ex)
                {
                    MessageBox.Show(this,
                        "No se pudo exportar el PDF:\n" + ex.Message,
                        "MDViewer", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                if (!ok)
                {
                    MessageBox.Show(this,
                        "No se pudo exportar el PDF.",
                        "MDViewer", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                }
            }
        }

        private void StartWatcher(string filePath)
        {
            StopWatcher();

            string dir = Path.GetDirectoryName(filePath);
            string file = Path.GetFileName(filePath);
            if (string.IsNullOrEmpty(dir) || string.IsNullOrEmpty(file))
            {
                return;
            }

            _debounceTimer = new System.Windows.Forms.Timer();
            _debounceTimer.Interval = 300;
            _debounceTimer.Tick += OnDebounceTick;

            _watcher = new FileSystemWatcher(dir, file);
            _watcher.NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.Size | NotifyFilters.CreationTime;
            _watcher.Changed += OnFileChangedOnDisk;
            _watcher.Renamed += OnFileChangedOnDisk;
            _watcher.EnableRaisingEvents = true;
        }

        private void StopWatcher()
        {
            if (_watcher != null)
            {
                _watcher.EnableRaisingEvents = false;
                _watcher.Dispose();
                _watcher = null;
            }
            if (_debounceTimer != null)
            {
                _debounceTimer.Stop();
                _debounceTimer.Dispose();
                _debounceTimer = null;
            }
        }

        private void OnFileChangedOnDisk(object sender, FileSystemEventArgs e)
        {
            if (IsDisposed)
            {
                return;
            }
            // FileSystemWatcher dispara en un hilo de threadpool: hay que
            // volver al hilo de UI antes de tocar el Timer o el WebView2.
            if (InvokeRequired)
            {
                BeginInvoke(new Action(RestartDebounceTimer));
            }
            else
            {
                RestartDebounceTimer();
            }
        }

        private void RestartDebounceTimer()
        {
            if (_debounceTimer == null)
            {
                return;
            }
            _debounceTimer.Stop();
            _debounceTimer.Start();
        }

        private async void OnDebounceTick(object sender, EventArgs e)
        {
            _debounceTimer.Stop();
            await RenderCurrentFileAsync();
        }

        private void OnFormClosed(object sender, FormClosedEventArgs e)
        {
            StopWatcher();
            if (_webView.CoreWebView2 != null)
            {
                _webView.CoreWebView2.WebMessageReceived -= OnWebMessageReceived;
                _webView.CoreWebView2.NavigationCompleted -= OnNavigationCompleted;
            }
            _webView.Dispose();
        }

        private void UpdateTitle()
        {
            string fileName = Path.GetFileName(_currentFilePath);
            Text = fileName + " - MDViewer";
        }

        private string PromptForFile()
        {
            using (OpenFileDialog dialog = new OpenFileDialog())
            {
                dialog.Filter = "Markdown (*.md;*.markdown)|*.md;*.markdown|Todos los archivos (*.*)|*.*";
                dialog.Title = "MDViewer - Abrir archivo";
                if (dialog.ShowDialog(this) == DialogResult.OK)
                {
                    return dialog.FileName;
                }
                return null;
            }
        }

        private static string LoadEmbeddedViewerHtml()
        {
            Assembly assembly = Assembly.GetExecutingAssembly();
            using (Stream stream = assembly.GetManifestResourceStream(ViewerResourceName))
            {
                if (stream == null)
                {
                    throw new InvalidOperationException(
                        "No se encontro el recurso embebido '" + ViewerResourceName + "'.");
                }
                using (StreamReader reader = new StreamReader(stream, Encoding.UTF8))
                {
                    return reader.ReadToEnd();
                }
            }
        }

        /// <summary>
        /// Carga el icono de marca embebido como recurso administrado (igual
        /// que assets\viewer.html) para usarlo en la barra de titulo y en la
        /// barra de tareas. Se pide un tamano concreto (32x32) en vez de
        /// dejar que System.Drawing.Icon elija: esa API interpreta mal la
        /// entrada PNG de 256 px del .ico (pide 256 y devuelve 128), y
        /// Icon.ExtractAssociatedIcon tiene el mismo problema por otra via
        /// (solo trae un tamano pequeno). Si el recurso no aparece, se deja
        /// el icono por defecto de WinForms: esto es cosmetico, no debe
        /// tumbar el visor.
        /// </summary>
        private static Icon LoadEmbeddedIcon()
        {
            try
            {
                Assembly assembly = Assembly.GetExecutingAssembly();
                using (Stream stream = assembly.GetManifestResourceStream(IconResourceName))
                {
                    if (stream == null)
                    {
                        return null;
                    }
                    return new Icon(stream, 32, 32);
                }
            }
            catch (Exception)
            {
                return null;
            }
        }

        /// <summary>
        /// Codifica una cadena .NET como literal de cadena JS/JSON, sin
        /// depender de ninguna libreria (no hay NuGet en este proyecto).
        /// </summary>
        private static string JsonEncodeString(string value)
        {
            if (value == null)
            {
                return "null";
            }

            StringBuilder sb = new StringBuilder(value.Length + 16);
            sb.Append('"');
            for (int i = 0; i < value.Length; i++)
            {
                char c = value[i];
                switch (c)
                {
                    case '"':
                        sb.Append("\\\"");
                        break;
                    case '\\':
                        sb.Append("\\\\");
                        break;
                    case '\b':
                        sb.Append("\\b");
                        break;
                    case '\f':
                        sb.Append("\\f");
                        break;
                    case '\n':
                        sb.Append("\\n");
                        break;
                    case '\r':
                        sb.Append("\\r");
                        break;
                    case '\t':
                        sb.Append("\\t");
                        break;
                    default:
                        // U+2028 y U+2029 son validos en JSON pero
                        // rompen un literal de cadena JS clasico si
                        // van sin escapar.
                        if (c < ' ' || c == '\u2028' || c == '\u2029')
                        {
                            sb.Append("\\u");
                            sb.Append(((int)c).ToString("x4"));
                        }
                        else
                        {
                            sb.Append(c);
                        }
                        break;
                }
            }
            sb.Append('"');
            return sb.ToString();
        }
    }

    /// <summary>
    /// Asociacion de .md con MDViewer, en HKCU:\Software\Classes (nunca
    /// HKLM ni HKCR). Auto-registro: no hay install.ps1 para esta app, el
    /// propio exe se ofrece a asociarse en su primer arranque.
    /// </summary>
    internal static class FileAssociation
    {
        private const string ProgId = "BSTools.MDViewer";
        private const string SettingsSubKey = "Software\\BSTools\\MDViewer";
        private const string AskedValueName = "AskedAssociation";

        private const uint ShcneAssocchanged = 0x08000000;
        private const uint ShcnfIdlist = 0x0000;

        [DllImport("shell32.dll")]
        private static extern void SHChangeNotify(uint wEventId, uint uFlags, IntPtr dwItem1, IntPtr dwItem2);

        private static bool _askedThisProcess;

        public static void MaybeOfferAssociation(IWin32Window owner)
        {
            if (_askedThisProcess)
            {
                return;
            }

            using (RegistryKey key = Registry.CurrentUser.OpenSubKey(SettingsSubKey))
            {
                if (key != null && key.GetValue(AskedValueName) != null)
                {
                    _askedThisProcess = true;
                    return;
                }
            }

            _askedThisProcess = true;

            DialogResult result = MessageBox.Show(owner,
                "MDViewer puede abrirse automaticamente al hacer doble clic en archivos " +
                ".md.\n\nQuieres asociar los archivos .md con MDViewer?",
                "MDViewer",
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Question);

            if (result == DialogResult.Yes)
            {
                Associate();
            }

            MarkAsked();
        }

        private static void MarkAsked()
        {
            using (RegistryKey key = Registry.CurrentUser.CreateSubKey(SettingsSubKey))
            {
                key.SetValue(AskedValueName, 1, RegistryValueKind.DWord);
            }
        }

        public static void Associate()
        {
            string exePath = Application.ExecutablePath;
            string command = "\"" + exePath + "\" \"%1\"";

            using (RegistryKey progIdKey = Registry.CurrentUser.CreateSubKey("Software\\Classes\\" + ProgId))
            {
                progIdKey.SetValue(string.Empty, "Documento Markdown (MDViewer)");
                using (RegistryKey shellKey = progIdKey.CreateSubKey("shell\\open\\command"))
                {
                    shellKey.SetValue(string.Empty, command);
                }
                // Apunta al .exe (no al .ico): la asociacion queda
                // autocontenida, si alguien borra MDViewer.ico los .md no
                // se quedan sin icono (el exe lleva su icono embebido via
                // /win32icon en build.ps1).
                using (RegistryKey iconKey = progIdKey.CreateSubKey("DefaultIcon"))
                {
                    iconKey.SetValue(string.Empty, "\"" + exePath + "\",0");
                }
            }

            using (RegistryKey openWithKey = Registry.CurrentUser.CreateSubKey(
                "Software\\Classes\\.md\\OpenWithProgids"))
            {
                openWithKey.SetValue(ProgId, new byte[0], RegistryValueKind.Binary);
            }

            bool hasUserChoice;
            using (RegistryKey userChoiceKey = Registry.CurrentUser.OpenSubKey(
                "Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\.md\\UserChoice"))
            {
                hasUserChoice = userChoiceKey != null;
            }

            // Windows protege UserChoice con un hash: si ya existe, no se
            // toca (falsificarlo no es honesto ni fiable). El usuario puede
            // seguir viendo el dialogo "Abrir con" hasta que elija MDViewer
            // el mismo, a mano.
            if (!hasUserChoice)
            {
                using (RegistryKey extKey = Registry.CurrentUser.CreateSubKey("Software\\Classes\\.md"))
                {
                    extKey.SetValue(string.Empty, ProgId);
                }
            }

            NotifyShellAssociationChanged();
        }

        public static void Disassociate()
        {
            SafeDeleteTree("Software\\Classes\\" + ProgId);

            using (RegistryKey openWithKey = Registry.CurrentUser.OpenSubKey(
                "Software\\Classes\\.md\\OpenWithProgids", true))
            {
                if (openWithKey != null && openWithKey.GetValue(ProgId) != null)
                {
                    openWithKey.DeleteValue(ProgId, false);
                }
            }

            using (RegistryKey extKey = Registry.CurrentUser.OpenSubKey("Software\\Classes\\.md", true))
            {
                if (extKey != null)
                {
                    object current = extKey.GetValue(string.Empty);
                    string currentProgId = current as string;
                    if (currentProgId != null && currentProgId.Equals(ProgId, StringComparison.OrdinalIgnoreCase))
                    {
                        extKey.DeleteValue(string.Empty, false);
                    }
                }
            }

            NotifyShellAssociationChanged();
        }

        /// <summary>
        /// Avisa al Explorador de que cambio una asociacion de archivos
        /// (icono incluido) para que lo refresque de inmediato, sin esperar
        /// a que reinicie por su cuenta ni a un logoff.
        /// </summary>
        private static void NotifyShellAssociationChanged()
        {
            SHChangeNotify(ShcneAssocchanged, ShcnfIdlist, IntPtr.Zero, IntPtr.Zero);
        }

        private static void SafeDeleteTree(string path)
        {
            try
            {
                Registry.CurrentUser.DeleteSubKeyTree(path);
            }
            catch (ArgumentException)
            {
                // La clave no existia; nada que borrar.
            }
        }
    }
}
