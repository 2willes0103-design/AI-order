/**
 * Google Apps Script - 餐廳庫進階版
 */

function doGet(e) {
  const action = e.parameter.action;
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  try {
    if (action === "get_status") {
      const config = getOrCreateSheet(ss, "Config", [["Key", "Value"], ["active_restaurant", ""]]);
      const activeRes = config.getRange(2, 2).getValue();
      let menuItems = [];
      if (activeRes) {
        const menuSheet = ss.getSheetByName("Menu");
        if (menuSheet) {
          const rawData = menuSheet.getDataRange().getValues();
          if (rawData.length > 1) {
            menuItems = rawData.slice(1).map(r => ({ name: r[0], price: r[1], category: r[2] }));
          }
        }
      }
      return response({ active_restaurant: activeRes, menu: menuItems });
    }

    if (action === "get_library") {
      const libSheet = ss.getSheetByName("Library");
      if (!libSheet) return response({ restaurants: [] });
      const data = libSheet.getDataRange().getValues();
      if (data.length <= 1) return response({ restaurants: [] });
      const names = [...new Set(data.slice(1).map(r => r[0]))];
      return response({ restaurants: names });
    }

    if (action === "get_menu_from_library") {
      const resName = e.parameter.name;
      const libSheet = ss.getSheetByName("Library");
      if (!libSheet) return response({ menu: [] });
      const rawData = libSheet.getDataRange().getValues();
      const menu = rawData.slice(1)
        .filter(r => r[0] === resName)
        .map(r => ({ name: r[1], price: r[2], category: r[3] }));
      return response({ menu: menu });
    }

    if (action === "init_orders_sheet") {
      const orderSheet = getOrCreateSheet(ss, "Orders", [["餐廳", "訂購人", "餐點", "數量", "金額", "備註"]]);
      orderSheet.getRange(1, 1, 1, 6).setValues([["餐廳", "訂購人", "餐點", "數量", "金額", "備註"]]);
      return response({ status: "success" });
    }

    if (action === "get_all_orders") {
      const orderSheet = ss.getSheetByName("Orders");
      if (!orderSheet) return response({ orders: [] });
      const rows = orderSheet.getDataRange().getValues();
      const orders = rows.slice(1).map(r => {
        // 判斷是新格式(6欄含金額)還是舊格式(5欄無金額)
        // 新格式：r[4] 是數字(金額)，r[5] 是備註
        // 舊格式：r[4] 是備註文字
        const col4IsAmount = r[4] !== '' && !isNaN(parseFloat(r[4]));
        return {
          restaurant: r[0] || '',
          user: r[1] || '',
          item: r[2] || '',
          qty: r[3] || 0,
          amount: col4IsAmount ? parseFloat(r[4]) : 0,
          note: col4IsAmount ? (r[5] || '') : (r[4] || '')
        };
      });
      return response({ orders: orders });
    }
  } catch (err) {
    return response({ error: err.toString() });
  }
}

function doPost(e) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  try {
    const data = JSON.parse(e.postData.contents);
    const action = data.action;

    if (action === "save_to_library") {
      const libSheet = getOrCreateSheet(ss, "Library", [["餐廳名稱", "品項", "價格", "分類"]]);
      // 刪除此餐廳舊有的記錄
      const rows = libSheet.getDataRange().getValues();
      for (let i = rows.length - 1; i >= 1; i--) {
        if (rows[i][0] === data.restaurant_name) libSheet.deleteRow(i + 1);
      }
      // 批次寫入新記錄
      const newRows = data.menu.map(item => [data.restaurant_name, item.name, item.price, item.category]);
      libSheet.getRange(libSheet.getLastRow() + 1, 1, newRows.length, 4).setValues(newRows);
      return response({ status: "success" });
    }

    if (action === "delete_from_library") {
      const libSheet = ss.getSheetByName("Library");
      if (!libSheet) return response({ status: "success" });
      const rows = libSheet.getDataRange().getValues();
      for (let i = rows.length - 1; i >= 1; i--) {
        if (rows[i][0] === data.restaurant_name) libSheet.deleteRow(i + 1);
      }
      return response({ status: "success" });
    }

    if (action === "set_active_restaurant") {
      const config = getOrCreateSheet(ss, "Config", [["Key", "Value"]]);
      config.getRange(2, 2).setValue(data.restaurant_name);
      
      const menuSheet = getOrCreateSheet(ss, "Menu", [["名稱", "價格", "分類"]]);
      menuSheet.clear();
      
      const rows = [["名稱", "價格", "分類"]];
      if (data.menu && data.menu.length > 0) {
        data.menu.forEach(item => rows.push([item.name, item.price, item.category || ""]));
        menuSheet.getRange(1, 1, rows.length, 3).setValues(rows);
      }
      return response({ status: "success" });
    }

    if (action === "submit_order") {
      const orderSheet = getOrCreateSheet(ss, "Orders", [["餐廳", "訂購人", "餐點", "數量", "金額", "備註"]]);
      // 確保標題列包含金額欄（相容舊版沒有金額的分頁）
      orderSheet.getRange(1, 1, 1, 6).setValues([["餐廳", "訂購人", "餐點", "數量", "金額", "備註"]]);
      if (data.items && data.items.length > 0) {
        const orderRows = data.items.map((item, index) => [
          data.restaurant_name || "",
          data.user_name,
          item.name,
          item.qty,
          (parseFloat(item.price) || 0) * item.qty,
          index === 0 ? (data.note || "") : ""
        ]);
        orderSheet.getRange(orderSheet.getLastRow() + 1, 1, orderRows.length, 6).setValues(orderRows);
      }
      return response({ status: "success" });
    }

    return response({ error: "未知指令: " + action });
  } catch (err) {
    return response({ error: "程式執行出錯: " + err.toString() });
  }
}

function response(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function getOrCreateSheet(ss, name, headers) {
  let sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
    if (headers && headers.length > 0) {
      sheet.getRange(1, 1, headers.length, headers[0].length).setValues(headers);
    }
  }
  return sheet;
}
