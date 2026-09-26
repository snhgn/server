/**
 * 图像处理与智能轻量化压缩工具
 * 用于前端壁纸/背景图片的自适应尺寸缩放与质量压缩，避免超出 localStorage 存储配额
 */
export function processImageFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith('image/')) {
      reject(new Error('请选择有效的图片文件 (支持 JPG / PNG / WebP / GIF)'))
      return
    }
    if (file.size > 20 * 1024 * 1024) {
      reject(new Error('图片过大，请选择 20MB 以内的图片'))
      return
    }

    const reader = new FileReader()
    reader.onerror = () => reject(new Error('读取图片文件失败'))
    reader.onload = () => {
      const rawDataUrl = reader.result
      if (typeof rawDataUrl !== 'string') {
        reject(new Error('解析图片格式失败'))
        return
      }

      // 如果是动图 GIF 或矢量图 SVG 且体积较小，保留原格式
      if ((file.type === 'image/gif' || file.type === 'image/svg+xml') && file.size < 2 * 1024 * 1024) {
        resolve(rawDataUrl)
        return
      }

      const img = new Image()
      img.onerror = () => reject(new Error('图片加载失败，可能格式不受支持或已损坏'))
      img.onload = () => {
        try {
          // 限制最大宽高在 1920 以内，既保证高清显示，又大幅削减体积
          const MAX_DIM = 1920
          let width = img.width
          let height = img.height

          if (width > MAX_DIM || height > MAX_DIM) {
            if (width > height) {
              height = Math.round((height * MAX_DIM) / width)
              width = MAX_DIM
            } else {
              width = Math.round((width * MAX_DIM) / height)
              height = MAX_DIM
            }
          }

          const canvas = document.createElement('canvas')
          canvas.width = width
          canvas.height = height
          const ctx = canvas.getContext('2d')
          if (!ctx) {
            resolve(rawDataUrl)
            return
          }

          ctx.drawImage(img, 0, 0, width, height)

          // PNG 保留透明度，其余压缩为高质量 JPEG
          const isPng = file.type === 'image/png'
          const mime = isPng ? 'image/png' : 'image/jpeg'
          const compressed = canvas.toDataURL(mime, 0.86)

          // 若原图本身已经足够小，优先使用原数据
          if (file.size < 1024 * 1024 && rawDataUrl.length <= compressed.length) {
            resolve(rawDataUrl)
          } else {
            resolve(compressed)
          }
        } catch {
          resolve(rawDataUrl)
        }
      }
      img.src = rawDataUrl
    }
    reader.readAsDataURL(file)
  })
}
