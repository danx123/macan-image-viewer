use numpy::{IntoPyArray, PyArray2, PyArray3, PyReadonlyArray2, PyReadonlyArray3};
// PENTING: pakai `numpy::ndarray` (re-export), JANGAN nambah dependency
// `ndarray` sendiri di Cargo.toml. Alasannya: crate `numpy` mendukung
// rentang versi ndarray yang semver-incompatible (0.15–0.17), dan kalau kita
// juga declare `ndarray` sendiri di Cargo.toml, Cargo bisa resolve DUA
// instance ndarray yang berbeda versi major-nya. Akibatnya `Array3<u8>` yang
// kita bikin jadi tipe yang beda secara teknis dari `ArrayBase` yang dipakai
// trait `IntoPyArray` di dalam numpy — makanya muncul error "no method named
// `into_pyarray` found". Dengan selalu pakai `numpy::ndarray::Array3`,
// versinya dijamin sama-sama satu instance dengan yang dipakai numpy.
use numpy::ndarray::{Array2, Array3};
use opencv::calib3d;
use opencv::core::{
    self, DMatch as CvDMatch, KeyPoint as CvKeyPoint, KeyPointTraitConst,
    Mat, Ptr, Scalar, CV_8UC1, CV_8UC3, CV_8UC4,
};
use opencv::features2d::{
    self, BFMatcher as CvBFMatcher, BFMatcherTraitConst,
    DescriptorMatcherTrait, DescriptorMatcherTraitConst,
    FlannBasedMatcher as CvFlannBasedMatcher, FlannBasedMatcherTrait,
    FlannBasedMatcherTraitConst, Feature2DTrait, Feature2DTraitConst, ORB as CvOrb,
    ORBTraitConst, ORBTrait,
};
use opencv::flann::{IndexParams, IndexParamsTrait, SearchParams};
use opencv::imgcodecs;
use opencv::imgproc;
use opencv::prelude::*; // MatTraitConst, MatTrait, MatTraitConstManual, dll.
use opencv::videoio::{self, VideoCapture as CvVideoCapture, VideoCaptureTrait, VideoCaptureTraitConst};
use pyo3::exceptions::PyValueError;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

// ============================================================================
// 🌉 JEMBATAN ERROR — opencv::Error dan pyo3::PyErr sama-sama tipe dari luar
// crate ini, jadi `impl From<opencv::Error> for PyErr` dilarang orphan rule
// (makanya `?` di fungsi ber-return PyResult<Mat> gagal compile). EngineError
// jadi perantara LOKAL: boleh punya `From` dari kedua sisi, dan pyo3 otomatis
// convert dia jadi PyErr lewat `impl From<EngineError> for PyErr` di bawah.
// ============================================================================
enum EngineError {
    Cv(opencv::Error),
    Py(PyErr),
}

impl From<opencv::Error> for EngineError {
    fn from(e: opencv::Error) -> Self {
        EngineError::Cv(e)
    }
}

impl From<PyErr> for EngineError {
    fn from(e: PyErr) -> Self {
        EngineError::Py(e)
    }
}

impl From<EngineError> for PyErr {
    fn from(e: EngineError) -> Self {
        match e {
            EngineError::Cv(e) => PyRuntimeError::new_err(e.to_string()),
            EngineError::Py(e) => e,
        }
    }
}

type CvResult<T> = Result<T, EngineError>;

// ============================================================================
// 🧱 PyMat — opencv::Mat BUKAN tipe PyO3 (bukan #[pyclass], gak ada
// IntoPy/FromPyObject), jadi gak pernah bisa lewat batas Python<->Rust
// langsung. PyMat bungkus Mat supaya bisa jadi parameter/return value
// pyfunction. Tiap fungsi di bawah "shadow" parameternya balik ke &Mat di
// baris pertama (`let src = &src.inner;`) supaya isi body PERSIS sama
// seperti sebelumnya — cuma signature & baris Ok(...) terakhir yang berubah.
// ============================================================================
// `unsendable`: opencv::Mat membungkus raw pointer (*mut c_void) yang gak
// Sync, jadi PyO3 gak bisa jamin PyMat aman dipakai lintas-thread secara
// otomatis. `unsendable` bikin instance-nya cuma boleh diakses dari thread
// Python yang bikin dia — cukup buat kasus kita karena semua fungsi di sini
// dipanggil sinkron dari satu thread Python yang sama.
// CATATAN: sempat nyoba tambahin attribute `from_py_object`/`skip_from_py_object`
// buat ngilangin warning deprecated di FromPyObject-via-Clone, TERNYATA versi
// pyo3 yang beneran ke-resolve di sini belum kenal attribute itu sama sekali
// (bukan salah satu opsi valid) — jadi dibiarin default aja (warning-nya gak
// bahaya, cuma warning, bukan error, dan default behavior-nya tetap bikin
// Vec<PyMat> di merge()/hconcat()/vconcat() bisa jalan).
#[pyclass(unsendable)]
#[derive(Clone)]
struct PyMat {
    inner: Mat,
}

impl From<Mat> for PyMat {
    fn from(m: Mat) -> Self {
        PyMat { inner: m }
    }
}

// ============================================================================
// 🔧 FUNGSI DASAR — SAMA PERSIS DENGAN cv2.*
// ============================================================================

/// cv2.imread() — Baca gambar dari file
#[pyfunction]
#[pyo3(signature = (path, flags=None))]
fn imread(path: &str, flags: Option<i32>) -> CvResult<PyMat> {
    let flags = flags.unwrap_or(imgcodecs::IMREAD_UNCHANGED);
    let mat = imgcodecs::imread(path, flags)?;
    if mat.empty() {
        return Err(PyValueError::new_err(format!(
            "Gagal baca gambar: {}", path
        ))
        .into());
    }
    Ok(mat.into())
}

/// cv2.imwrite() — Simpan gambar ke file
#[pyfunction]
#[pyo3(signature = (path, img, params=None))]
fn imwrite(path: &str, img: &PyMat, params: Option<Vec<i32>>) -> CvResult<bool> {
    let img = &img.inner;
    // imgcodecs::imwrite butuh &opencv::core::Vector<i32>, bukan &Vec<i32> —
    // Vec biasa gak auto-convert, jadi kita bungkus eksplisit di sini.
    let params: core::Vector<i32> = core::Vector::from(params.unwrap_or_default());
    let result = imgcodecs::imwrite(path, img, &params)?;
    Ok(result)
}

/// cv2.cvtColor() — Ubah ruang warna
#[pyfunction]
#[pyo3(signature = (src, code, dst_cn=0))]
fn cvt_color(src: &PyMat, code: i32, dst_cn: i32) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    imgproc::cvt_color(src, &mut dst, code, dst_cn)?;
    Ok(dst.into())
}

/// cv2.resize() — Ubah ukuran gambar
#[pyfunction]
#[pyo3(signature = (src, dsize=None, fx=0.0, fy=0.0, interpolation=None))]
fn resize(
    src: &PyMat,
    dsize: Option<(i32, i32)>,
    fx: f64,
    fy: f64,
    interpolation: Option<i32>,
) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    let dsize = match dsize {
        Some((w, h)) => core::Size::new(w, h),
        None => core::Size::new(0, 0),
    };
    let interpolation = interpolation.unwrap_or(imgproc::INTER_LINEAR);
    imgproc::resize(src, &mut dst, dsize, fx, fy, interpolation)?;
    Ok(dst.into())
}

/// cv2.rotate() — Putar gambar 90/180 derajat
#[pyfunction]
fn rotate(src: &PyMat, rotate_code: i32) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    core::rotate(src, &mut dst, rotate_code)?;
    Ok(dst.into())
}

/// cv2.flip() — Balik gambar (horizontal/vertikal/keduanya)
#[pyfunction]
fn flip(src: &PyMat, flip_code: i32) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    core::flip(src, &mut dst, flip_code)?;
    Ok(dst.into())
}

/// cv2.addWeighted() — Campur dua gambar dengan bobot
#[pyfunction]
#[pyo3(signature = (src1, alpha, src2, beta, gamma, dst=None))]
fn add_weighted(
    src1: &PyMat,
    alpha: f64,
    src2: &PyMat,
    beta: f64,
    gamma: f64,
    dst: Option<&mut PyMat>,
) -> CvResult<PyMat> {
    let src1 = &src1.inner;
    let src2 = &src2.inner;
    match dst {
        Some(d) => {
            core::add_weighted(src1, alpha, src2, beta, gamma, &mut d.inner, -1)?;
            Ok(d.inner.clone().into())
        }
        None => {
            let mut d = Mat::default();
            core::add_weighted(src1, alpha, src2, beta, gamma, &mut d, -1)?;
            Ok(d.into())
        }
    }
}

// ============================================================================
// 🎨 FUNGSI EFEK DASAR (untuk macan_efek.py)
// ============================================================================

/// cv2.GaussianBlur()
#[pyfunction]
#[pyo3(signature = (src, ksize, sigma_x, sigma_y=0.0, border_type=None))]
fn gaussian_blur(
    src: &PyMat,
    ksize: (i32, i32),
    sigma_x: f64,
    sigma_y: f64,
    border_type: Option<i32>,
) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    let ksize = core::Size::new(ksize.0, ksize.1);
    let border_type = border_type.unwrap_or(core::BORDER_DEFAULT);
    imgproc::gaussian_blur(src, &mut dst, ksize, sigma_x, sigma_y, border_type)?;
    Ok(dst.into())
}

/// cv2.filter2D() — Pakai kernel kustom (sharpen, emboss, dll)
#[pyfunction]
#[pyo3(signature = (src, ddepth, kernel, anchor=None, delta=0.0, border_type=None))]
fn filter_2d(
    src: &PyMat,
    ddepth: i32,
    kernel: &PyMat,
    anchor: Option<(i32, i32)>,
    delta: f64,
    border_type: Option<i32>,
) -> CvResult<PyMat> {
    let src = &src.inner;
    let kernel = &kernel.inner;
    let mut dst = Mat::default();
    let anchor = match anchor {
        Some((x, y)) => core::Point::new(x, y),
        None => core::Point::new(-1, -1),
    };
    let border_type = border_type.unwrap_or(core::BORDER_DEFAULT);
    imgproc::filter_2d(src, &mut dst, ddepth, kernel, anchor, delta, border_type)?;
    Ok(dst.into())
}

/// cv2.bilateralFilter() — Blur tapi tetap tajam di tepi
#[pyfunction]
#[pyo3(signature = (src, d, sigma_color, sigma_space, border_type=None))]
fn bilateral_filter(
    src: &PyMat,
    d: i32,
    sigma_color: f64,
    sigma_space: f64,
    border_type: Option<i32>,
) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    let border_type = border_type.unwrap_or(core::BORDER_DEFAULT);
    imgproc::bilateral_filter(src, &mut dst, d, sigma_color, sigma_space, border_type)?;
    Ok(dst.into())
}

/// cv2.medianBlur()
#[pyfunction]
fn median_blur(src: &PyMat, ksize: i32) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    imgproc::median_blur(src, &mut dst, ksize)?;
    Ok(dst.into())
}

/// cv2.applyColorMap() — Buat efek warna keren
#[pyfunction]
fn apply_color_map(src: &PyMat, colormap: i32) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    imgproc::apply_color_map(src, &mut dst, colormap)?;
    Ok(dst.into())
}

/// cv2.convertScaleAbs() — Atur brightness/contrast
#[pyfunction]
#[pyo3(signature = (src, alpha=1.0, beta=0.0))]
fn convert_scale_abs(src: &PyMat, alpha: f64, beta: f64) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    core::convert_scale_abs(src, &mut dst, alpha, beta)?;
    Ok(dst.into())
}

/// cv2.LUT() — Lookup table (buat gamma correction, posterize, dll)
#[pyfunction]
fn lut(src: &PyMat, lut: &PyMat) -> CvResult<PyMat> {
    let src = &src.inner;
    let lut = &lut.inner;
    let mut dst = Mat::default();
    core::lut(src, lut, &mut dst)?;
    Ok(dst.into())
}

/// cv2.split() — Pisah channel BGR(A)
#[pyfunction]
fn split(src: &PyMat) -> CvResult<Vec<PyMat>> {
    let src = &src.inner;
    // Compiler gak bisa nebak T di Vector<T> cuma dari `.default()` — kasih
    // tipe eksplisit Vector<Mat>, sama kayak yang dipakai di equalize_hist().
    let mut mv: core::Vector<Mat> = core::Vector::new();
    core::split(src, &mut mv)?;
    Ok(mv.to_vec().into_iter().map(PyMat::from).collect())
}

/// cv2.merge() — Gabung channel jadi satu gambar
#[pyfunction]
fn merge(mv: Vec<PyMat>) -> CvResult<PyMat> {
    // Vec<&PyMat> gak bisa lagi jadi argumen #[pyfunction] langsung di pyo3
    // versi baru (perlu FromPyObject utuh, bukan reference) — jadi diterima
    // sebagai Vec<PyMat> (masing-masing di-clone pas extract dari Python).
    let vec: core::Vector<Mat> = core::Vector::from_iter(mv.iter().map(|m| m.inner.clone()));
    let mut dst = Mat::default();
    core::merge(&vec, &mut dst)?;
    Ok(dst.into())
}

/// cv2.bitwise_not() — Invert warna
#[pyfunction]
fn bitwise_not(src: &PyMat) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    core::bitwise_not(src, &mut dst, &core::no_array())?;
    Ok(dst.into())
}

/// cv2.bitwise_and() — dipakai buat masking (mis. efek cartoon)
#[pyfunction]
#[pyo3(signature = (src1, src2, mask=None))]
fn bitwise_and(src1: &PyMat, src2: &PyMat, mask: Option<&PyMat>) -> CvResult<PyMat> {
    let src1 = &src1.inner;
    let src2 = &src2.inner;
    let mask = mask.map(|m| &m.inner);
    let mut dst = Mat::default();
    match mask {
        Some(m) => core::bitwise_and(src1, src2, &mut dst, m)?,
        None => core::bitwise_and(src1, src2, &mut dst, &core::no_array())?,
    }
    Ok(dst.into())
}

/// cv2.add() dengan skalar (mis. cv2.add(channel, 25)) — otomatis saturate 0-255
#[pyfunction]
fn add_scalar(src: &PyMat, value: f64) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    core::add(src, &Scalar::all(value), &mut dst, &core::no_array(), -1)?;
    Ok(dst.into())
}

/// cv2.subtract() dengan skalar — otomatis saturate 0-255
#[pyfunction]
fn subtract_scalar(src: &PyMat, value: f64) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    core::subtract(src, &Scalar::all(value), &mut dst, &core::no_array(), -1)?;
    Ok(dst.into())
}

/// cv2.divide() — dipakai buat pencil sketch (color dodge)
#[pyfunction]
#[pyo3(signature = (src1, src2, scale=1.0))]
fn divide(src1: &PyMat, src2: &PyMat, scale: f64) -> CvResult<PyMat> {
    let src1 = &src1.inner;
    let src2 = &src2.inner;
    let mut dst = Mat::default();
    core::divide2(src1, src2, &mut dst, scale, -1)?;
    Ok(dst.into())
}

/// cv2.transform() — dipakai buat efek sepia (kali matriks warna 3x3)
#[pyfunction]
fn transform(src: &PyMat, m: &PyMat) -> CvResult<PyMat> {
    let src = &src.inner;
    let m = &m.inner;
    let mut dst = Mat::default();
    core::transform(src, &mut dst, m)?;
    Ok(dst.into())
}

/// cv2.hconcat() — gabung gambar secara horizontal (collage)
#[pyfunction]
fn hconcat(mats: Vec<PyMat>) -> CvResult<PyMat> {
    let vec: core::Vector<Mat> = core::Vector::from_iter(mats.iter().map(|m| m.inner.clone()));
    let mut dst = Mat::default();
    core::hconcat(&vec, &mut dst)?;
    Ok(dst.into())
}

/// cv2.vconcat() — gabung gambar secara vertikal (collage)
#[pyfunction]
fn vconcat(mats: Vec<PyMat>) -> CvResult<PyMat> {
    let vec: core::Vector<Mat> = core::Vector::from_iter(mats.iter().map(|m| m.inner.clone()));
    let mut dst = Mat::default();
    core::vconcat(&vec, &mut dst)?;
    Ok(dst.into())
}

/// cv2.Canny() — deteksi tepi
#[pyfunction]
#[pyo3(signature = (src, threshold1, threshold2, aperture_size=3, l2gradient=false))]
fn canny(
    src: &PyMat,
    threshold1: f64,
    threshold2: f64,
    aperture_size: i32,
    l2gradient: bool,
) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    imgproc::canny(src, &mut dst, threshold1, threshold2, aperture_size, l2gradient)?;
    Ok(dst.into())
}

/// cv2.HoughLinesP() — Probabilistic Hough line transform.
///
/// Beda dari cv2: nggak ada array numpy shape (N,1,4) yang harus di-unwrap
/// pakai `line[0]` di sisi Python — di sini langsung balikin list of
/// (x1, y1, x2, y2) tuple, atau `None` kalau nggak ada garis ketemu (biar
/// pattern `if lines is not None:` di kode Python yang lama tetap kepake
/// tanpa perubahan behavior).
#[pyfunction]
#[pyo3(signature = (src, rho, theta, threshold, min_line_length=0.0, max_line_gap=0.0))]
fn hough_lines_p(
    src: &PyMat,
    rho: f64,
    theta: f64,
    threshold: i32,
    min_line_length: f64,
    max_line_gap: f64,
) -> CvResult<Option<Vec<(i32, i32, i32, i32)>>> {
    let src = &src.inner;
    let mut lines_mat = Mat::default();
    imgproc::hough_lines_p(
        src,
        &mut lines_mat,
        rho,
        theta,
        threshold,
        min_line_length,
        max_line_gap,
    )?;

    if lines_mat.rows() == 0 {
        return Ok(None);
    }

    let mut out = Vec::with_capacity(lines_mat.rows() as usize);
    for i in 0..lines_mat.rows() {
        // Tiap baris Mat hasil HoughLinesP adalah satu Vec4i: [x1, y1, x2, y2]
        let v = *lines_mat.at::<core::Vec4i>(i)?;
        out.push((v[0], v[1], v[2], v[3]));
    }
    Ok(Some(out))
}

/// cv2.adaptiveThreshold() — dipakai buat garis tepi efek cartoon
#[pyfunction]
fn adaptive_threshold(
    src: &PyMat,
    max_value: f64,
    adaptive_method: i32,
    threshold_type: i32,
    block_size: i32,
    c: f64,
) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    imgproc::adaptive_threshold(src, &mut dst, max_value, adaptive_method, threshold_type, block_size, c)?;
    Ok(dst.into())
}

// ============================================================================
// 🔁 JEMBATAN numpy <-> opencv::Mat
// Supaya macan_efek.py tetap bisa kerja dengan np.ndarray (buat QImage, PIL,
// slicing canvas kolase, dll) tanpa perlu cv2 sama sekali.
// ============================================================================

/// numpy (H, W, C) uint8 -> Mat. Array WAJIB contiguous (np.ascontiguousarray).
#[pyfunction]
fn numpy_to_mat(array: PyReadonlyArray3<u8>) -> CvResult<PyMat> {
    let arr = array.as_array();
    let shape = arr.shape();
    let (h, w, c) = (shape[0] as i32, shape[1] as i32, shape[2] as i32);
    let cv_type = match c {
        1 => CV_8UC1,
        3 => CV_8UC3,
        4 => CV_8UC4,
        _ => {
            return Err(PyValueError::new_err(
                "numpy_to_mat hanya mendukung array dengan 1, 3, atau 4 channel",
            )
            .into())
        }
    };
    let data = arr.as_slice().ok_or_else(|| {
        PyValueError::new_err(
            "Array harus contiguous — bungkus dengan np.ascontiguousarray() dulu",
        )
    })?;
    let mat = unsafe {
        Mat::new_rows_cols_with_data(h, w, cv_type, data.as_ptr() as *mut std::ffi::c_void, core::Mat_AUTO_STEP)?
    };
    // Clone supaya Mat memegang datanya sendiri — buffer numpy asal bisa
    // didealokasi/berubah kapan saja dari sisi Python.
    Ok(mat.try_clone()?.into())
}

/// Mat -> numpy (H, W, C) uint8. Channel 1 tetap dikembalikan sebagai (H, W, 1),
/// di-squeeze di sisi Python kalau perlu.
#[pyfunction]
fn mat_to_numpy<'py>(py: Python<'py>, mat: &PyMat) -> CvResult<Bound<'py, PyArray3<u8>>> {
    let mat = &mat.inner;
    let rows = mat.rows();
    let cols = mat.cols();
    let channels = mat.channels();
    let bytes = mat.data_bytes()?;
    let arr = Array3::from_shape_vec(
        (rows as usize, cols as usize, channels as usize),
        bytes.to_vec(),
    )
    .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok(arr.into_pyarray_bound(py))
}

// ============================================================================
// 🎛️ FUNGSI EFEK TINGKAT TINGGI (mengganti method ImageEffects yang lama)
// ============================================================================

/// Grayscale yang otomatis aware BGR/BGRA (dulunya image_proc_rust.manual_grayscale)
#[pyfunction]
fn manual_grayscale(src: &PyMat) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    if src.channels() == 4 {
        let mut bgr = Mat::default();
        imgproc::cvt_color(src, &mut bgr, imgproc::COLOR_BGRA2BGR, 0)?;
        imgproc::cvt_color(&bgr, &mut dst, imgproc::COLOR_BGR2GRAY, 0)?;
    } else {
        imgproc::cvt_color(src, &mut dst, imgproc::COLOR_BGR2GRAY, 0)?;
    }
    Ok(dst.into())
}

/// Efek sepia, alpha channel (kalau ada) tetap dipertahankan
/// (dulunya image_proc_rust.apply_sepia)
#[pyfunction]
fn apply_sepia(src: &PyMat) -> CvResult<PyMat> {
    let src = &src.inner;
    let kernel = Mat::from_slice_2d(&[
        &[0.272f32, 0.534, 0.131],
        &[0.349, 0.686, 0.168],
        &[0.393, 0.769, 0.189],
    ])?;

    if src.channels() == 4 {
        let mut bgr = Mat::default();
        imgproc::cvt_color(src, &mut bgr, imgproc::COLOR_BGRA2BGR, 0)?;
        let mut sepia = Mat::default();
        core::transform(&bgr, &mut sepia, &kernel)?;

        let mut src_channels = core::Vector::<Mat>::new();
        core::split(src, &mut src_channels)?;
        let alpha = src_channels.get(3)?;

        let mut sepia_channels = core::Vector::<Mat>::new();
        core::split(&sepia, &mut sepia_channels)?;
        sepia_channels.push(alpha);

        let mut out = Mat::default();
        core::merge(&sepia_channels, &mut out)?;
        Ok(out.into())
    } else {
        let mut sepia = Mat::default();
        core::transform(src, &mut sepia, &kernel)?;
        Ok(sepia.into())
    }
}

/// Gamma correction lewat LUT (dulunya dihitung manual di Python)
#[pyfunction]
fn adjust_gamma(src: &PyMat, gamma: f64) -> CvResult<PyMat> {
    let src = &src.inner;
    if gamma <= 0.0 || (gamma - 1.0).abs() < 1e-6 {
        return Ok(src.try_clone()?.into());
    }
    let inv_gamma = 1.0 / gamma;
    let mut table_vals = [0u8; 256];
    for (i, slot) in table_vals.iter_mut().enumerate() {
        let v = ((i as f64) / 255.0).powf(inv_gamma) * 255.0;
        *slot = v.round().clamp(0.0, 255.0) as u8;
    }
    let table = Mat::from_slice(&table_vals)?;
    let mut dst = Mat::default();
    core::lut(src, &table, &mut dst)?;
    Ok(dst.into())
}

/// Brightness + contrast dalam satu panggilan (convertScaleAbs)
#[pyfunction]
#[pyo3(signature = (src, brightness=0.0, contrast=1.0))]
fn adjust_brightness_contrast(src: &PyMat, brightness: f64, contrast: f64) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    core::convert_scale_abs(src, &mut dst, contrast, brightness)?;
    Ok(dst.into())
}

/// Saturasi lewat HSV (split S, skala, merge lagi)
#[pyfunction]
fn adjust_saturation(src: &PyMat, factor: f64) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut hsv = Mat::default();
    imgproc::cvt_color(src, &mut hsv, imgproc::COLOR_BGR2HSV, 0)?;

    let mut channels = core::Vector::<Mat>::new();
    core::split(&hsv, &mut channels)?;
    let s = channels.get(1)?;
    let mut s_scaled = Mat::default();
    core::convert_scale_abs(&s, &mut s_scaled, factor, 0.0)?;
    channels.set(1, s_scaled)?;

    let mut merged = Mat::default();
    core::merge(&channels, &mut merged)?;
    let mut dst = Mat::default();
    imgproc::cvt_color(&merged, &mut dst, imgproc::COLOR_HSV2BGR, 0)?;
    Ok(dst.into())
}

/// Geser Hue (0-179 di OpenCV 8-bit HSV)
#[pyfunction]
fn adjust_hue(src: &PyMat, shift: i32) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut hsv = Mat::default();
    imgproc::cvt_color(src, &mut hsv, imgproc::COLOR_BGR2HSV, 0)?;

    let mut channels = core::Vector::<Mat>::new();
    core::split(&hsv, &mut channels)?;
    let h = channels.get(0)?;
    let mut h_shifted = Mat::default();
    core::add(&h, &Scalar::all(shift as f64), &mut h_shifted, &core::no_array(), -1)?;
    channels.set(0, h_shifted)?;

    let mut merged = Mat::default();
    core::merge(&channels, &mut merged)?;
    let mut dst = Mat::default();
    imgproc::cvt_color(&merged, &mut dst, imgproc::COLOR_HSV2BGR, 0)?;
    Ok(dst.into())
}

/// Geser channel R/G/B satu-satu, masing-masing -100..100 (auto-saturate)
#[pyfunction]
fn adjust_channel_mixer(src: &PyMat, r_shift: f64, g_shift: f64, b_shift: f64) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut channels = core::Vector::<Mat>::new();
    core::split(src, &mut channels)?;

    let mut b = channels.get(0)?;
    let mut g = channels.get(1)?;
    let mut r = channels.get(2)?;

    if b_shift != 0.0 {
        let mut out = Mat::default();
        core::add(&b, &Scalar::all(b_shift), &mut out, &core::no_array(), -1)?;
        b = out;
    }
    if g_shift != 0.0 {
        let mut out = Mat::default();
        core::add(&g, &Scalar::all(g_shift), &mut out, &core::no_array(), -1)?;
        g = out;
    }
    if r_shift != 0.0 {
        let mut out = Mat::default();
        core::add(&r, &Scalar::all(r_shift), &mut out, &core::no_array(), -1)?;
        r = out;
    }

    let mut merged_vec = core::Vector::<Mat>::new();
    merged_vec.push(b);
    merged_vec.push(g);
    merged_vec.push(r);
    if channels.len() == 4 {
        merged_vec.push(channels.get(3)?);
    }

    let mut dst = Mat::default();
    core::merge(&merged_vec, &mut dst)?;
    Ok(dst.into())
}

/// Vignette (gelap di pinggir). Catatan: hanya menggelapkan 3 channel pertama
/// (B, G, R) — kalau input BGRA, alpha tidak diubah.
#[pyfunction]
#[pyo3(signature = (src, sigma=200.0))]
fn apply_vignette(src: &PyMat, sigma: f64) -> CvResult<PyMat> {
    let src = &src.inner;
    let rows = src.rows();
    let cols = src.cols();

    let kx = imgproc::get_gaussian_kernel(cols, sigma, core::CV_64F)?;
    let ky = imgproc::get_gaussian_kernel(rows, sigma, core::CV_64F)?;
    let kx_data = kx.data_typed::<f64>()?;
    let ky_data = ky.data_typed::<f64>()?;

    let mut mask = vec![0f64; (rows as usize) * (cols as usize)];
    let mut max_val = 0f64;
    for y in 0..rows as usize {
        for x in 0..cols as usize {
            let v = ky_data[y] * kx_data[x];
            mask[y * cols as usize + x] = v;
            if v > max_val {
                max_val = v;
            }
        }
    }
    if max_val <= 0.0 {
        max_val = 1.0;
    }

    let mut dst = src.try_clone()?;
    for y in 0..rows {
        for x in 0..cols {
            let factor = mask[(y as usize) * (cols as usize) + (x as usize)] / max_val;
            if let Ok(px) = dst.at_2d_mut::<core::Vec3b>(y, x) {
                for c in 0..3 {
                    px[c] = ((px[c] as f64) * factor).round().clamp(0.0, 255.0) as u8;
                }
            }
        }
    }
    Ok(dst.into())
}

/// Sharpen dengan kernel 3x3 standar [[-1,-1,-1],[-1,9,-1],[-1,-1,-1]]
#[pyfunction]
fn apply_sharpen(src: &PyMat) -> CvResult<PyMat> {
    let src = &src.inner;
    let kernel = Mat::from_slice_2d(&[
        &[-1f32, -1.0, -1.0],
        &[-1.0, 9.0, -1.0],
        &[-1.0, -1.0, -1.0],
    ])?;
    let mut dst = Mat::default();
    imgproc::filter_2d(src, &mut dst, -1, &kernel, core::Point::new(-1, -1), 0.0, core::BORDER_DEFAULT)?;
    Ok(dst.into())
}

/// Unsharp mask (sharpen berbasis Gaussian blur, lebih halus dari filter2D biasa)
#[pyfunction]
#[pyo3(signature = (src, amount=1.0, radius=5, threshold=0))]
fn apply_unsharp_mask(src: &PyMat, amount: f64, radius: i32, threshold: i32) -> CvResult<PyMat> {
    let src = &src.inner;
    let k = if radius % 2 == 0 { radius + 1 } else { radius }.max(1);
    let mut blurred = Mat::default();
    imgproc::gaussian_blur(src, &mut blurred, core::Size::new(k, k), 0.0, 0.0, core::BORDER_DEFAULT)?;
    let mut dst = Mat::default();
    core::add_weighted(src, 1.0 + amount, &blurred, -amount, 0.0, &mut dst, -1)?;
    let _ = threshold; // reserved: bisa dipakai buat masking area low-contrast nanti
    Ok(dst.into())
}

/// Equalize histogram — kalau gambar berwarna, disamakan lewat channel Y (YCrCb)
/// biar warnanya tidak rusak.
#[pyfunction]
fn equalize_hist(src: &PyMat) -> CvResult<PyMat> {
    let src = &src.inner;
    let mut dst = Mat::default();
    if src.channels() == 1 {
        imgproc::equalize_hist(src, &mut dst)?;
    } else {
        let mut ycrcb = Mat::default();
        imgproc::cvt_color(src, &mut ycrcb, imgproc::COLOR_BGR2YCrCb, 0)?;
        let mut ch = core::Vector::<Mat>::new();
        core::split(&ycrcb, &mut ch)?;
        let mut y_eq = Mat::default();
        imgproc::equalize_hist(&ch.get(0)?, &mut y_eq)?;
        ch.set(0, y_eq)?;
        let mut merged = Mat::default();
        core::merge(&ch, &mut merged)?;
        imgproc::cvt_color(&merged, &mut dst, imgproc::COLOR_YCrCb2BGR, 0)?;
    }
    Ok(dst.into())
}

// ============================================================================
// 🧭 FITUR & MATCHING — ORB, BFMatcher, FlannBasedMatcher, findHomography.
// Ditambahkan untuk Macan Image Finder (reverse image search berbasis
// ORB + RANSAC), supaya app itu bisa lepas total dari `import cv2`.
//
// KONVENSI PENTING beda dari fungsi2 di atas: descriptor ORB (matrix N x 32
// uint8) sengaja DIBALIKIN LANGSUNG sebagai numpy array (bukan PyMat), karena
// sisi Python (macan_image_finder) nyimpen descriptor itu ke SQLite lewat
// operasi numpy murni (.dtype, .astype, .tobytes(), np.frombuffer(...)) —
// motongin butuh bungkus/bongkar PyMat bolak-balik yang gak perlu.
// KeyPoint & DMatch juga dibikin PyO3 class sendiri (bukan lewat opencv::core
// punya) karena field-nya (pt, size, angle, response, octave, class_id /
// queryIdx, trainIdx, distance) dipakai langsung sebagai atribut Python biasa
// di serialize_keypoints() & di loop pencocokan — jadi lebih gampang expose
// sebagai struct data polos daripada nge-wrap boxed type opencv::core.
// ============================================================================

/// Tiruan cv2.KeyPoint — cuma data biasa (pt, size, angle, response, octave,
/// class_id), dibuat dari hasil ORB.detect_and_compute() atau langsung dari
/// Python (deserialize_keypoints menciptakan ulang lewat konstruktor ini).
#[pyclass(name = "KeyPoint")]
#[derive(Clone, Copy)]
struct PyKeyPoint {
    x: f32,
    y: f32,
    #[pyo3(get, set)]
    size: f32,
    #[pyo3(get, set)]
    angle: f32,
    #[pyo3(get, set)]
    response: f32,
    #[pyo3(get, set)]
    octave: i32,
    #[pyo3(get, set)]
    class_id: i32,
}

#[pymethods]
impl PyKeyPoint {
    /// cv2.KeyPoint(x=, y=, size=, angle=, response=, octave=, class_id=)
    #[new]
    #[pyo3(signature = (x, y, size, angle=-1.0, response=0.0, octave=0, class_id=-1))]
    fn new(x: f32, y: f32, size: f32, angle: f32, response: f32, octave: i32, class_id: i32) -> Self {
        PyKeyPoint { x, y, size, angle, response, octave, class_id }
    }

    /// kp.pt — tuple (x, y), sama seperti cv2.KeyPoint.pt
    #[getter]
    fn pt(&self) -> (f32, f32) {
        (self.x, self.y)
    }
}

impl From<&CvKeyPoint> for PyKeyPoint {
    fn from(kp: &CvKeyPoint) -> Self {
        let pt = kp.pt();
        PyKeyPoint {
            x: pt.x,
            y: pt.y,
            size: kp.size(),
            angle: kp.angle(),
            response: kp.response(),
            octave: kp.octave(),
            class_id: kp.class_id(),
        }
    }
}

/// Tiruan cv2.DMatch — hasil dari knn_match(). Beda dari cv2 asli, field-nya
/// snake_case (query_idx/train_idx/img_idx/distance) mengikuti konvensi
/// method di seluruh image_engine (lihat VideoCapture.is_opened() dkk).
/// CATATAN: beda dari KeyPoint (boxed class, diakses lewat trait
/// KeyPointTraitConst), DMatch di opencv-rust adalah "simple struct" —
/// field C++-nya (queryIdx/trainIdx/imgIdx/distance) diekspos LANGSUNG
/// sebagai public field Rust, bukan lewat trait getter yang me-return Result.
#[pyclass(name = "DMatch")]
#[derive(Clone, Copy)]
struct PyDMatch {
    #[pyo3(get)]
    query_idx: i32,
    #[pyo3(get)]
    train_idx: i32,
    #[pyo3(get)]
    img_idx: i32,
    #[pyo3(get)]
    distance: f32,
}

impl From<&CvDMatch> for PyDMatch {
    fn from(m: &CvDMatch) -> Self {
        PyDMatch {
            query_idx: m.query_idx,
            train_idx: m.train_idx,
            img_idx: m.img_idx,
            distance: m.distance,
        }
    }
}

/// numpy (N, 32) uint8 -> Mat CV_8UC1. Dipakai buat masukin descriptor ORB
/// (yang disimpan/dipulihkan sisi Python sebagai numpy array) ke pemanggilan
/// DescriptorMatcher milik OpenCV.
fn descriptors_to_mat(array: &PyReadonlyArray2<u8>) -> CvResult<Mat> {
    let arr = array.as_array();
    let shape = arr.shape();
    let (rows, cols) = (shape[0] as i32, shape[1] as i32);
    let data = arr.as_slice().ok_or_else(|| {
        PyValueError::new_err("Descriptor harus contiguous — pakai np.ascontiguousarray() dulu")
    })?;
    let mat = unsafe {
        Mat::new_rows_cols_with_data(rows, cols, CV_8UC1, data.as_ptr() as *mut std::ffi::c_void, core::Mat_AUTO_STEP)?
    };
    Ok(mat.try_clone()?)
}

/// Mat CV_8UC1 (N x 32) -> numpy (N, 32) uint8. Kebalikan dari
/// descriptors_to_mat(), dipakai buat balikin hasil ORB.detect_and_compute().
fn mat_to_descriptors<'py>(py: Python<'py>, mat: &Mat) -> CvResult<Bound<'py, PyArray2<u8>>> {
    let rows = mat.rows() as usize;
    let cols = mat.cols() as usize;
    let bytes = mat.data_bytes()?;
    let arr = Array2::from_shape_vec((rows, cols), bytes.to_vec())
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok(arr.into_pyarray_bound(py))
}

/// Jalanin knn_match generik buat BFMatcher maupun FlannBasedMatcher — dua-duanya
/// implement trait yang sama (DescriptorMatcherTrait), jadi logikanya cukup
/// ditulis sekali di sini.
///
/// CATATAN BUILD: DescriptorMatcher C++ (cv::DescriptorMatcher::knnMatch)
/// punya 2 overload — satu yang pakai train-set yang sudah di-add() ke
/// matcher, satu lagi yang terima trainDescriptors eksplisit (ini yang kita
/// pakai, biar sama kayak `flann.knnMatch(query_des, db_des, k=2)` di kode
/// Python lama). Binding
/// generator opencv-rust biasanya kasih nama method kedua ini `knn_train_match`.
/// Kalau pas `cargo build` ternyata nama methodnya beda (mis. `knn_match_1`),
/// tinggal ganti nama panggilan di bawah ini saja — jangan ubah bagian lain.
fn run_knn_match(
    matcher: &mut impl DescriptorMatcherTrait,
    query_des: PyReadonlyArray2<u8>,
    train_des: PyReadonlyArray2<u8>,
    k: i32,
) -> CvResult<Vec<Vec<PyDMatch>>> {
    let query_mat = descriptors_to_mat(&query_des)?;
    let train_mat = descriptors_to_mat(&train_des)?;

    let mut matches: core::Vector<core::Vector<CvDMatch>> = core::Vector::new();
    matcher.knn_train_match(&query_mat, &train_mat, &mut matches, k, &core::no_array(), false)?;

    let mut out = Vec::with_capacity(matches.len());
    for row in matches.iter() {
        let mut row_out = Vec::with_capacity(row.len());
        for m in row.iter() {
            row_out.push(PyDMatch::from(&m));
        }
        out.push(row_out);
    }
    Ok(out)
}

/// cv2.ORB — feature detector + descriptor extractor.
#[pyclass(name = "ORB", unsendable)]
struct Orb {
    inner: Ptr<CvOrb>,
}

/// cv2.ORB_create(nfeatures=..., ...) — parameter lain disediakan biar
/// lengkap, tapi macan_image_finder cuma pernah pakai `nfeatures`.
#[pyfunction]
#[pyo3(signature = (
    nfeatures=500, scale_factor=1.2, nlevels=8, edge_threshold=31,
    first_level=0, wta_k=2, patch_size=31, fast_threshold=20
))]
fn orb_create(
    nfeatures: i32,
    scale_factor: f32,
    nlevels: i32,
    edge_threshold: i32,
    first_level: i32,
    wta_k: i32,
    patch_size: i32,
    fast_threshold: i32,
) -> CvResult<Orb> {
    let inner = CvOrb::create(
        nfeatures,
        scale_factor,
        nlevels,
        edge_threshold,
        first_level,
        wta_k,
        features2d::ORB_ScoreType::HARRIS_SCORE,
        patch_size,
        fast_threshold,
    )?;
    Ok(Orb { inner })
}

#[pymethods]
impl Orb {
    /// orb.detect_and_compute(image, mask) — mirip cv2 `detectAndCompute`,
    /// balikin (list[KeyPoint], descriptors atau None kalau kosong).
    #[pyo3(signature = (image, mask=None))]
    fn detect_and_compute<'py>(
        &mut self,
        py: Python<'py>,
        image: &PyMat,
        mask: Option<&PyMat>,
    ) -> CvResult<(Vec<PyKeyPoint>, Option<Bound<'py, PyArray2<u8>>>)> {
        let image = &image.inner;
        let mask_mat = match mask {
            Some(m) => m.inner.clone(),
            None => Mat::default(),
        };
        let mut keypoints: core::Vector<CvKeyPoint> = core::Vector::new();
        let mut descriptors = Mat::default();
        self.inner
            .detect_and_compute(image, &mask_mat, &mut keypoints, &mut descriptors, false)?;

        let py_keypoints: Vec<PyKeyPoint> = keypoints.iter().map(|kp| PyKeyPoint::from(&kp)).collect();

        if descriptors.empty() || descriptors.rows() == 0 {
            return Ok((py_keypoints, None));
        }
        Ok((py_keypoints, Some(mat_to_descriptors(py, &descriptors)?)))
    }
}

/// cv2.BFMatcher(normType, crossCheck) — brute-force descriptor matcher.
#[pyclass(name = "BFMatcher", unsendable)]
struct PyBfMatcher {
    inner: CvBFMatcher,
}

#[pymethods]
impl PyBfMatcher {
    #[new]
    #[pyo3(signature = (norm_type=core::NORM_HAMMING, cross_check=false))]
    fn new(norm_type: i32, cross_check: bool) -> CvResult<Self> {
        Ok(PyBfMatcher { inner: CvBFMatcher::new(norm_type, cross_check)? })
    }

    fn knn_match(
        &mut self,
        query_des: PyReadonlyArray2<u8>,
        train_des: PyReadonlyArray2<u8>,
        k: i32,
    ) -> CvResult<Vec<Vec<PyDMatch>>> {
        run_knn_match(&mut self.inner, query_des, train_des, k)
    }
}

/// cv2.FlannBasedMatcher(index_params, search_params) — dikonfigurasi lewat
/// dict Python persis seperti cv2 (mis. algorithm=6/LSH buat descriptor
/// biner ORB). Dipetakan ke `cv::flann::IndexParams`/`SearchParams` generik
/// (bukan subclass LshIndexParams) supaya gak perlu upcast Ptr yang ribet.
#[pyclass(name = "FlannBasedMatcher", unsendable)]
struct PyFlannBasedMatcher {
    inner: CvFlannBasedMatcher,
}

#[pymethods]
impl PyFlannBasedMatcher {
    #[new]
    fn new(index_params: &Bound<'_, PyDict>, search_params: &Bound<'_, PyDict>) -> CvResult<Self> {
        fn get_i32(d: &Bound<'_, PyDict>, key: &str, default: i32) -> i32 {
            d.get_item(key)
                .ok()
                .flatten()
                .and_then(|v| v.extract::<i32>().ok())
                .unwrap_or(default)
        }

        // algorithm=6 -> FLANN_INDEX_LSH, cocok buat descriptor biner ORB
        // (persis nilai yang dipakai index_params di SearchWorker Python).
        let algorithm = get_i32(index_params, "algorithm", 6);
        let table_number = get_i32(index_params, "table_number", 6);
        let key_size = get_i32(index_params, "key_size", 12);
        let multi_probe_level = get_i32(index_params, "multi_probe_level", 1);
        let checks = get_i32(search_params, "checks", 32);

        let mut idx = IndexParams::default()?;
        idx.set_algorithm(algorithm)?;
        idx.set_int("table_number", table_number)?;
        idx.set_int("key_size", key_size)?;
        idx.set_int("multi_probe_level", multi_probe_level)?;
        let idx_ptr = Ptr::new(idx);

        let search = SearchParams::new(checks, 0.0, true, false)?;
        let search_ptr = Ptr::new(search);

        Ok(PyFlannBasedMatcher {
            inner: CvFlannBasedMatcher::new(&idx_ptr, &search_ptr)?,
        })
    }

    fn knn_match(
        &mut self,
        query_des: PyReadonlyArray2<u8>,
        train_des: PyReadonlyArray2<u8>,
        k: i32,
    ) -> CvResult<Vec<Vec<PyDMatch>>> {
        run_knn_match(&mut self.inner, query_des, train_des, k)
    }
}

/// cv2.findHomography(srcPoints, dstPoints, method, ransacReprojThreshold)
/// — src/dst_points diterima sebagai numpy float32 shape (N, 1, 2), persis
/// bentuk yang dihasilkan `np.float32([...]).reshape(-1, 1, 2)` di kode
/// Python lama. Balikin (M, mask): M None kalau homography gagal dihitung,
/// mask numpy uint8 shape (N, 1) — bisa langsung dipanggil `.ravel().sum()`.
#[pyfunction]
#[pyo3(signature = (src_points, dst_points, method=0, ransac_reproj_threshold=3.0))]
fn find_homography<'py>(
    py: Python<'py>,
    src_points: PyReadonlyArray3<f32>,
    dst_points: PyReadonlyArray3<f32>,
    method: i32,
    ransac_reproj_threshold: f64,
) -> CvResult<(Option<PyMat>, Option<Bound<'py, PyArray2<u8>>>)> {
    let src_arr = src_points.as_array();
    let dst_arr = dst_points.as_array();
    let n = src_arr.shape()[0];

    let mut src_vec: core::Vector<core::Point2f> = core::Vector::with_capacity(n);
    let mut dst_vec: core::Vector<core::Point2f> = core::Vector::with_capacity(n);
    for i in 0..n {
        src_vec.push(core::Point2f::new(src_arr[[i, 0, 0]], src_arr[[i, 0, 1]]));
        dst_vec.push(core::Point2f::new(dst_arr[[i, 0, 0]], dst_arr[[i, 0, 1]]));
    }

    let mut mask = Mat::default();
    // CATATAN BUILD: urutan parameter di sini ngikutin urutan deklarasi C++
    // (src, dst, method, ransacReprojThreshold, mask). Kalau signature hasil
    // bindgen opencv-rust ternyata naruh `mask` di posisi lain, tinggal
    // sesuaikan urutan argumen panggilan ini saja.
    let h = calib3d::find_homography(&src_vec, &dst_vec, &mut mask, method, ransac_reproj_threshold)?;

    if h.empty() {
        return Ok((None, None));
    }

    let mask_rows = mask.rows() as usize;
    let mask_bytes = mask.data_bytes()?;
    let mask_arr = Array2::from_shape_vec((mask_rows, 1), mask_bytes.to_vec())
        .map_err(|e| PyValueError::new_err(e.to_string()))?;

    Ok((Some(h.into()), Some(mask_arr.into_pyarray_bound(py))))
}

// ============================================================================
// 🎬 VIDEOCAPTURE — SAMA PERSIS DENGAN cv2.VideoCapture (dipakai buat baca
// metadata video: fps, resolusi, bitrate, dll — bukan buat decode frame).
// Perlu opencv_videoio dinyalakan di build (lihat config.toml).
// ============================================================================

/// cv2.VideoCapture — buka file video, bisa baca properti (cap.get) DAN
/// decode frame (cap.read())
// Sama kayak PyMat: opencv::videoio::VideoCapture juga bungkus raw pointer
// yang gak Sync, jadi perlu `unsendable`.
#[pyclass(unsendable)]
struct VideoCapture {
    inner: CvVideoCapture,
}

#[pymethods]
impl VideoCapture {
    /// VideoCapture(path) — otomatis pilih backend terbaik yang tersedia (CAP_ANY)
    // 🔓 GIL FIX: buka file video (probing container/codec) bisa makan waktu
    // gak sebentar. Kalau GIL gak dilepas, thread lain (termasuk main/GUI
    // thread) ketahan nunggu meski VideoCapture ini dipanggil dari QThread
    // worker — makanya sebelumnya cursor jadi "muter"/busy pas hover video.
    #[new]
    fn new(py: Python<'_>, path: &str) -> CvResult<Self> {
        let inner = py.allow_threads(|| CvVideoCapture::from_file(path, videoio::CAP_ANY))?;
        Ok(Self { inner })
    }

    /// cap.isOpened()
    fn is_opened(&self) -> CvResult<bool> {
        Ok(self.inner.is_opened()?)
    }

    /// 🔍 DEBUG: cap.getBackendName() — buat mastiin backend apa yang
    /// SEBENARNYA kepilih dari CAP_ANY (FFMPEG vs MSMF vs lainnya). Kalau
    /// hover video "gak gerak" (seek gak efektif), ini cara paling pasti
    /// buat konfirmasi apakah backend-nya beda dari yang dipakai cv2 biasa.
    fn backend_name(&self) -> CvResult<String> {
        Ok(self.inner.get_backend_name()?)
    }

    /// cap.get(prop_id) — pakai konstanta CAP_PROP_* di bawah
    fn get(&self, prop_id: i32) -> CvResult<f64> {
        Ok(self.inner.get(prop_id)?)
    }

    /// cap.set(prop_id, value) — jarang dipakai buat baca metadata, tapi disediakan biar lengkap
    // 🔓 GIL FIX: set(CAP_PROP_POS_FRAMES, ...) = seek, dan seek berbasis
    // frame number sering butuh decode ulang dari keyframe terdekat —
    // tergantung GOP codec-nya bisa ratusan ms s/d detik. Ini SUMBER UTAMA
    // busy cursor saat hover: dipanggil 8x per hover (lihat
    // VideoHoverPreviewWorker.run()), dan tanpa allow_threads, GIL disandera
    // penuh durasi seek itu tiap kali dipanggil, walau dari background thread.
    fn set(&mut self, py: Python<'_>, prop_id: i32, value: f64) -> CvResult<bool> {
        Ok(py.allow_threads(|| self.inner.set(prop_id, value))?)
    }

    /// cap.read() — decode frame berikutnya. MIRIP cv2: return (success, frame).
    /// Kalau gagal/EOF, success=False dan frame=None (persis pola
    /// `ret, frame = cap.read()` di cv2, biar gampang portingnya).
    // 🔓 GIL FIX: decode 1 frame juga blocking I/O+CPU (demux+decode).
    // Sama seperti set(), ini harus lepas GIL selama proses berlangsung,
    // supaya main thread tetap bisa proses event Qt (mouse move, paint, dll)
    // walau worker thread lagi sibuk decode di background.
    fn read(&mut self, py: Python<'_>) -> CvResult<(bool, Option<PyMat>)> {
        let mut frame = Mat::default();
        let inner = &mut self.inner;
        let success = py.allow_threads(|| inner.read(&mut frame))?;
        if success && !frame.empty() {
            Ok((true, Some(frame.into())))
        } else {
            Ok((false, None))
        }
    }

    /// cap.release()
    fn release(&mut self) -> CvResult<()> {
        self.inner.release()?;
        Ok(())
    }

    /// Dukungan `with VideoCapture(path) as cap:` — opsional tapi enak dipakai
    fn __enter__(slf: PyRefMut<'_, Self>) -> PyRefMut<'_, Self> {
        slf
    }

    #[pyo3(signature = (_exc_type=None, _exc_value=None, _traceback=None))]
    fn __exit__(
        &mut self,
        _exc_type: Option<Bound<'_, PyAny>>,
        _exc_value: Option<Bound<'_, PyAny>>,
        _traceback: Option<Bound<'_, PyAny>>,
    ) -> CvResult<()> {
        self.release()
    }
}

// ============================================================================
// 📦 DAFTARKAN SEMUA KE MODUL PYTHON + KONSTANTA
// ============================================================================

#[pymodule]
fn image_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // --- Tipe ---
    m.add_class::<PyMat>()?;

    // --- Fungsi dasar ---
    m.add_function(wrap_pyfunction!(imread, m)?)?;
    m.add_function(wrap_pyfunction!(imwrite, m)?)?;
    m.add_function(wrap_pyfunction!(cvt_color, m)?)?;
    m.add_function(wrap_pyfunction!(resize, m)?)?;
    m.add_function(wrap_pyfunction!(rotate, m)?)?;
    m.add_function(wrap_pyfunction!(flip, m)?)?;
    m.add_function(wrap_pyfunction!(add_weighted, m)?)?;

    // --- Fungsi efek dasar (mirror cv2) ---
    m.add_function(wrap_pyfunction!(gaussian_blur, m)?)?;
    m.add_function(wrap_pyfunction!(filter_2d, m)?)?;
    m.add_function(wrap_pyfunction!(bilateral_filter, m)?)?;
    m.add_function(wrap_pyfunction!(median_blur, m)?)?;
    m.add_function(wrap_pyfunction!(apply_color_map, m)?)?;
    m.add_function(wrap_pyfunction!(convert_scale_abs, m)?)?;
    m.add_function(wrap_pyfunction!(lut, m)?)?;
    m.add_function(wrap_pyfunction!(split, m)?)?;
    m.add_function(wrap_pyfunction!(merge, m)?)?;
    m.add_function(wrap_pyfunction!(bitwise_not, m)?)?;
    m.add_function(wrap_pyfunction!(bitwise_and, m)?)?;
    m.add_function(wrap_pyfunction!(add_scalar, m)?)?;
    m.add_function(wrap_pyfunction!(subtract_scalar, m)?)?;
    m.add_function(wrap_pyfunction!(divide, m)?)?;
    m.add_function(wrap_pyfunction!(transform, m)?)?;
    m.add_function(wrap_pyfunction!(hconcat, m)?)?;
    m.add_function(wrap_pyfunction!(vconcat, m)?)?;
    m.add_function(wrap_pyfunction!(canny, m)?)?;
    m.add_function(wrap_pyfunction!(adaptive_threshold, m)?)?;
	m.add_function(wrap_pyfunction!(hough_lines_p, m)?)?;

    // --- Jembatan numpy <-> Mat ---
    m.add_function(wrap_pyfunction!(numpy_to_mat, m)?)?;
    m.add_function(wrap_pyfunction!(mat_to_numpy, m)?)?;

    // --- VideoCapture (metadata video) ---
    m.add_class::<VideoCapture>()?;

    // --- Fitur & matching (Macan Image Finder: ORB + RANSAC) ---
    m.add_class::<PyKeyPoint>()?;
    m.add_class::<PyDMatch>()?;
    m.add_class::<Orb>()?;
    m.add_class::<PyBfMatcher>()?;
    m.add_class::<PyFlannBasedMatcher>()?;
    m.add_function(wrap_pyfunction!(orb_create, m)?)?;
    m.add_function(wrap_pyfunction!(find_homography, m)?)?;

    // --- Fungsi efek tingkat tinggi ---
    m.add_function(wrap_pyfunction!(manual_grayscale, m)?)?;
    m.add_function(wrap_pyfunction!(apply_sepia, m)?)?;
    m.add_function(wrap_pyfunction!(adjust_gamma, m)?)?;
    m.add_function(wrap_pyfunction!(adjust_brightness_contrast, m)?)?;
    m.add_function(wrap_pyfunction!(adjust_channel_mixer, m)?)?;
    m.add_function(wrap_pyfunction!(adjust_saturation, m)?)?;
    m.add_function(wrap_pyfunction!(adjust_hue, m)?)?;
    m.add_function(wrap_pyfunction!(apply_vignette, m)?)?;
    m.add_function(wrap_pyfunction!(apply_sharpen, m)?)?;
    m.add_function(wrap_pyfunction!(apply_unsharp_mask, m)?)?;
    m.add_function(wrap_pyfunction!(equalize_hist, m)?)?;

    // --- KONSTANTA — SAMA PERSIS DENGAN cv2.* ---
    // imread flags
    m.add("IMREAD_UNCHANGED", imgcodecs::IMREAD_UNCHANGED)?;
    m.add("IMREAD_COLOR", imgcodecs::IMREAD_COLOR)?;
    m.add("IMREAD_GRAYSCALE", imgcodecs::IMREAD_GRAYSCALE)?;

    // imwrite flags
    m.add("IMWRITE_JPEG_QUALITY", imgcodecs::IMWRITE_JPEG_QUALITY)?;
    m.add("IMWRITE_WEBP_QUALITY", imgcodecs::IMWRITE_WEBP_QUALITY)?;
    m.add("IMWRITE_PNG_COMPRESSION", imgcodecs::IMWRITE_PNG_COMPRESSION)?;

    // Color conversion codes
    m.add("COLOR_BGR2RGB", imgproc::COLOR_BGR2RGB)?;
    m.add("COLOR_RGB2BGR", imgproc::COLOR_RGB2BGR)?;
    m.add("COLOR_BGR2GRAY", imgproc::COLOR_BGR2GRAY)?;
    m.add("COLOR_GRAY2BGR", imgproc::COLOR_GRAY2BGR)?;
    m.add("COLOR_BGRA2RGBA", imgproc::COLOR_BGRA2RGBA)?;
    m.add("COLOR_RGBA2BGRA", imgproc::COLOR_RGBA2BGRA)?;
    m.add("COLOR_BGR2BGRA", imgproc::COLOR_BGR2BGRA)?;
    m.add("COLOR_BGRA2BGR", imgproc::COLOR_BGRA2BGR)?;
    m.add("COLOR_BGR2HSV", imgproc::COLOR_BGR2HSV)?;
    m.add("COLOR_HSV2BGR", imgproc::COLOR_HSV2BGR)?;
    m.add("COLOR_BGR2LAB", imgproc::COLOR_BGR2Lab)?;
    m.add("COLOR_LAB2BGR", imgproc::COLOR_Lab2BGR)?;
    m.add("COLOR_BGR2YCrCb", imgproc::COLOR_BGR2YCrCb)?;
    m.add("COLOR_YCrCb2BGR", imgproc::COLOR_YCrCb2BGR)?;

    // Interpolation
    m.add("INTER_NEAREST", imgproc::INTER_NEAREST)?;
    m.add("INTER_LINEAR", imgproc::INTER_LINEAR)?;
    m.add("INTER_AREA", imgproc::INTER_AREA)?;
    m.add("INTER_CUBIC", imgproc::INTER_CUBIC)?;
    m.add("INTER_LANCZOS4", imgproc::INTER_LANCZOS4)?;

    // Rotate
    m.add("ROTATE_90_CLOCKWISE", core::ROTATE_90_CLOCKWISE)?;
    m.add("ROTATE_90_COUNTERCLOCKWISE", core::ROTATE_90_COUNTERCLOCKWISE)?;
    m.add("ROTATE_180", core::ROTATE_180)?;

    // Color maps
    m.add("COLORMAP_JET", imgproc::COLORMAP_JET)?;
    m.add("COLORMAP_VIRIDIS", imgproc::COLORMAP_VIRIDIS)?;
    m.add("COLORMAP_INFERNO", imgproc::COLORMAP_INFERNO)?;
    m.add("COLORMAP_MAGMA", imgproc::COLORMAP_MAGMA)?;
    m.add("COLORMAP_PLASMA", imgproc::COLORMAP_PLASMA)?;
    m.add("COLORMAP_COOL", imgproc::COLORMAP_COOL)?;
    m.add("COLORMAP_HOT", imgproc::COLORMAP_HOT)?;
    m.add("COLORMAP_PARULA", imgproc::COLORMAP_PARULA)?;
    m.add("COLORMAP_RAINBOW", imgproc::COLORMAP_RAINBOW)?;
    m.add("COLORMAP_OCEAN", imgproc::COLORMAP_OCEAN)?;

    // Border types
    m.add("BORDER_DEFAULT", core::BORDER_DEFAULT)?;
    m.add("BORDER_CONSTANT", core::BORDER_CONSTANT)?;
    m.add("BORDER_REFLECT", core::BORDER_REFLECT)?;
    m.add("BORDER_REPLICATE", core::BORDER_REPLICATE)?;

    // Threshold — dipakai efek cartoon (adaptiveThreshold)
    m.add("ADAPTIVE_THRESH_MEAN_C", imgproc::ADAPTIVE_THRESH_MEAN_C)?;
    m.add("ADAPTIVE_THRESH_GAUSSIAN_C", imgproc::ADAPTIVE_THRESH_GAUSSIAN_C)?;
    m.add("THRESH_BINARY", imgproc::THRESH_BINARY)?;
    m.add("THRESH_BINARY_INV", imgproc::THRESH_BINARY_INV)?;

    // VideoCapture properties — dipakai buat baca metadata video (fps, resolusi, dll)
    m.add("CAP_PROP_FRAME_COUNT", videoio::CAP_PROP_FRAME_COUNT)?;
    m.add("CAP_PROP_FPS", videoio::CAP_PROP_FPS)?;
    m.add("CAP_PROP_FRAME_WIDTH", videoio::CAP_PROP_FRAME_WIDTH)?;
    m.add("CAP_PROP_FRAME_HEIGHT", videoio::CAP_PROP_FRAME_HEIGHT)?;
    m.add("CAP_PROP_FOURCC", videoio::CAP_PROP_FOURCC)?;
    m.add("CAP_PROP_BITRATE", videoio::CAP_PROP_BITRATE)?;
    m.add("CAP_PROP_BRIGHTNESS", videoio::CAP_PROP_BRIGHTNESS)?;
    m.add("CAP_PROP_CONTRAST", videoio::CAP_PROP_CONTRAST)?;
    m.add("CAP_PROP_SATURATION", videoio::CAP_PROP_SATURATION)?;
    m.add("CAP_PROP_POS_FRAMES", videoio::CAP_PROP_POS_FRAMES)?;
    m.add("CAP_PROP_POS_MSEC", videoio::CAP_PROP_POS_MSEC)?;
    m.add("CAP_ANY", videoio::CAP_ANY)?;

    // Matching (Macan Image Finder)
    m.add("NORM_HAMMING", core::NORM_HAMMING)?;
    m.add("RANSAC", calib3d::RANSAC)?;

    Ok(())
}